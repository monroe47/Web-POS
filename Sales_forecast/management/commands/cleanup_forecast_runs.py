from django.core.management.base import BaseCommand
from django.conf import settings
import os

try:
    from Sales_forecast.models import ForecastRun
except Exception:
    ForecastRun = None

class Command(BaseCommand):
    help = "Cleanup persisted ForecastRun artifacts created during tests."

    def add_arguments(self, parser):
        parser.add_argument('--keep-last', type=int, default=0, help='Keep the most recent N runs (default 0)')

    def handle(self, *args, **options):
        if ForecastRun is None:
            self.stderr.write('ForecastRun model not available. Nothing to clean.')
            return

        keep_last = options.get('keep_last', 0)
        runs = ForecastRun.objects.order_by('-created_at')
        to_delete = runs[keep_last:]
        if not to_delete:
            self.stdout.write('No runs to delete.')
            return

        count = 0
        for r in to_delete:
            artifact = r.artifact_path
            r_id = r.id
            try:
                r.delete()
                count += 1
                if artifact:
                    try:
                        if os.path.exists(artifact):
                            os.remove(artifact)
                            self.stdout.write(f'Removed artifact for run {r_id}: {artifact}')
                    except Exception as e:
                        self.stderr.write(f'Failed to remove artifact {artifact}: {e}')
            except Exception as e:
                self.stderr.write(f'Failed to delete ForecastRun id={r_id}: {e}')

        self.stdout.write(self.style.SUCCESS(f'Deleted {count} ForecastRun(s).'))
