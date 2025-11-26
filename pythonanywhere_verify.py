"""
PythonAnywhere Post-Deployment Verification Script

Run this AFTER deployment to verify everything is working correctly.
Run from PythonAnywhere Bash console:

cd /home/username/your-repo
source venv/bin/activate
python pythonanywhere_verify.py
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'POSwithSalesForecast.settings_production')
django.setup()

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
CHECK = '✓'
CROSS = '✗'

class PythonAnywhereTester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.base_dir = Path(__file__).resolve().parent
    
    def header(self, title):
        print(f"\n{BLUE}{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}{RESET}\n")
    
    def success(self, msg):
        self.passed += 1
        print(f"{GREEN}{CHECK}{RESET} {msg}")
    
    def error(self, msg):
        self.failed += 1
        print(f"{RED}{CROSS}{RESET} {msg}")
    
    def warn(self, msg):
        print(f"{YELLOW}⚠{RESET} {msg}")
    
    def test_django_settings(self):
        self.header("1. Django Settings")
        
        from django.conf import settings
        
        # Check DEBUG
        if not settings.DEBUG:
            self.success("DEBUG = False (Production mode)")
        else:
            self.error("DEBUG = True (Should be False)")
        
        # Check ALLOWED_HOSTS
        if settings.ALLOWED_HOSTS and len(settings.ALLOWED_HOSTS) > 0:
            self.success(f"ALLOWED_HOSTS configured: {settings.ALLOWED_HOSTS[0]}")
        else:
            self.error("ALLOWED_HOSTS empty")
        
        # Check STATIC_ROOT
        if settings.STATIC_ROOT:
            if os.path.exists(settings.STATIC_ROOT):
                self.success(f"STATIC_ROOT exists: {settings.STATIC_ROOT}")
            else:
                self.error(f"STATIC_ROOT missing: {settings.STATIC_ROOT}")
        
        # Check MEDIA_ROOT
        if settings.MEDIA_ROOT:
            if os.path.exists(settings.MEDIA_ROOT):
                self.success(f"MEDIA_ROOT exists: {settings.MEDIA_ROOT}")
            else:
                self.warn(f"MEDIA_ROOT missing (will be created): {settings.MEDIA_ROOT}")
                os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    
    def test_database(self):
        self.header("2. Database")
        
        try:
            from django.db import connection
            from Account_management.models import Account
            
            # Test connection
            connection.ensure_connection()
            self.success("Database connection working")
            
            # Count users
            user_count = Account.objects.count()
            self.success(f"Database accessible ({user_count} users)")
            
        except Exception as e:
            self.error(f"Database error: {str(e)}")
    
    def test_apps(self):
        self.header("3. Installed Apps")
        
        from django.conf import settings
        
        required_apps = [
            'django.contrib.admin',
            'django.contrib.auth',
            'Inventory',
            'POS',
            'Account_management',
            'Sales_forecast',
        ]
        
        for app in required_apps:
            if app in settings.INSTALLED_APPS:
                self.success(f"App loaded: {app}")
            else:
                self.error(f"App missing: {app}")
    
    def test_static_files(self):
        self.header("4. Static Files")
        
        from django.conf import settings
        
        static_files_to_check = [
            'admin/css/base.css',
            'admin/js/admin/base.js',
        ]
        
        for file in static_files_to_check:
            full_path = os.path.join(settings.STATIC_ROOT, file)
            if os.path.exists(full_path):
                self.success(f"Static file exists: {file}")
            else:
                self.warn(f"Static file missing: {file}")
        
        # Check if staticfiles directory has content
        if os.path.exists(settings.STATIC_ROOT):
            file_count = sum([len(files) for r, d, files in os.walk(settings.STATIC_ROOT)])
            if file_count > 0:
                self.success(f"Staticfiles directory has {file_count} files")
            else:
                self.error("Staticfiles directory is empty - run collectstatic")
    
    def test_migrations(self):
        self.header("5. Migrations")
        
        from django.core.management import call_command
        from io import StringIO
        
        try:
            # Check for unapplied migrations
            out = StringIO()
            call_command('showmigrations', verbosity=0, stdout=out)
            
            output = out.getvalue()
            if '[ ]' not in output:  # [ ] means unapplied
                self.success("All migrations applied")
            else:
                self.warn("Some migrations are not applied - run migrate")
        except Exception as e:
            self.error(f"Migration check failed: {str(e)}")
    
    def test_imports(self):
        self.header("6. Key Module Imports")
        
        modules_to_test = [
            ('django', 'Django'),
            ('rest_framework', 'Django REST Framework'),
            ('pandas', 'Pandas'),
            ('sklearn', 'Scikit-learn'),
            ('xgboost', 'XGBoost'),
            ('pmdarima', 'PMDarima (ARIMA)'),
            ('joblib', 'Joblib'),
            ('gunicorn', 'Gunicorn'),
        ]
        
        for module, name in modules_to_test:
            try:
                __import__(module)
                self.success(f"{name} available")
            except ImportError:
                self.error(f"{name} not installed")
    
    def test_environment(self):
        self.header("7. Environment Variables")
        
        # Check DJANGO_SETTINGS_MODULE
        settings_module = os.environ.get('DJANGO_SETTINGS_MODULE')
        if settings_module == 'POSwithSalesForecast.settings_production':
            self.success(f"DJANGO_SETTINGS_MODULE: {settings_module}")
        else:
            self.warn(f"DJANGO_SETTINGS_MODULE: {settings_module}")
        
        # Check DEBUG env var
        debug_env = os.environ.get('DEBUG', 'not set')
        self.success(f"DEBUG env var: {debug_env}")
        
        # Check if DJANGO_SECRET_KEY is set
        if 'DJANGO_SECRET_KEY' in os.environ:
            secret = os.environ.get('DJANGO_SECRET_KEY')
            if 'insecure' not in secret.lower():
                self.success("Custom DJANGO_SECRET_KEY configured")
            else:
                self.error("DJANGO_SECRET_KEY is default (insecure)")
        else:
            self.warn("DJANGO_SECRET_KEY env variable not set")
    
    def test_customizations(self):
        self.header("8. Custom Settings")
        
        from django.conf import settings
        
        # Check custom user model
        if settings.AUTH_USER_MODEL == 'Account_management.Account':
            self.success("Custom user model configured")
        else:
            self.warn(f"User model: {settings.AUTH_USER_MODEL}")
        
        # Check login URL
        if hasattr(settings, 'LOGIN_URL'):
            self.success(f"Login URL: {settings.LOGIN_URL}")
        
        # Check forecast models
        forecast_dir = settings.FORECAST_MODELS_DIR if hasattr(settings, 'FORECAST_MODELS_DIR') else None
        if forecast_dir:
            if os.path.exists(forecast_dir):
                models = os.listdir(forecast_dir)
                self.success(f"Forecast models directory ({len(models)} files)")
            else:
                self.warn("Forecast models directory doesn't exist yet")
    
    def test_admin(self):
        self.header("9. Admin Interface")
        
        from django.contrib.admin.sites import site
        
        registered_models = len(site._registry)
        if registered_models > 0:
            self.success(f"Admin interface configured ({registered_models} models)")
        else:
            self.error("No models registered in admin")
    
    def test_urls(self):
        self.header("10. URL Configuration")
        
        from django.urls import reverse, NoReverseMatch
        
        urls_to_test = [
            ('admin:index', 'Admin'),
            ('pos:dashboard', 'POS Dashboard'),
        ]
        
        for url_name, label in urls_to_test:
            try:
                reverse(url_name)
                self.success(f"URL reversed: {label}")
            except NoReverseMatch:
                self.warn(f"URL not found: {label}")
            except Exception as e:
                self.warn(f"URL error ({label}): {str(e)[:50]}")
    
    def print_summary(self):
        self.header("DEPLOYMENT VERIFICATION SUMMARY")
        
        print(f"{GREEN}✓ Passed: {self.passed}{RESET}")
        if self.failed > 0:
            print(f"{RED}✗ Failed: {self.failed}{RESET}")
        
        print(f"\nTotal: {self.passed + self.failed} tests")
        
        if self.failed == 0:
            print(f"\n{GREEN}✓ Deployment successful!{RESET}")
            print("\nYour PythonAnywhere deployment is ready to use.")
            print("Visit: https://username.pythonanywhere.com")
            return True
        else:
            print(f"\n{RED}✗ Fix the above issues{RESET}")
            return False
    
    def run_all_tests(self):
        self.header("PythonAnywhere Deployment Verification")
        
        try:
            self.test_django_settings()
            self.test_database()
            self.test_apps()
            self.test_static_files()
            self.test_migrations()
            self.test_imports()
            self.test_environment()
            self.test_customizations()
            self.test_admin()
            self.test_urls()
            
            return self.print_summary()
        except Exception as e:
            print(f"\n{RED}Fatal error during testing:{RESET}")
            print(f"{str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    tester = PythonAnywhereTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
