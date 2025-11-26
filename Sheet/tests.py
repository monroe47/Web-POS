from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

class SheetViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(username='sheetuser', full_name='Sheet User', password='sheetpassword')
        self.user.is_active = True
        self.user.save()
        self.client.login(username='sheetuser', password='sheetpassword')

    def test_sheet_view_loads(self):
        """Test that the sheet_view loads correctly and uses the correct template."""
        response = self.client.get(reverse('sheet:excel')) # Corrected URL name
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'Sheet/Spreadsheet.html') # Corrected template name

    def test_spreadsheet_dashboard_loads(self):
        """Test that the spreadsheet_dashboard loads correctly and uses the correct template."""
        response = self.client.get(reverse('sheet:spreadsheet_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'Sheet/Spreadsheet.html')
