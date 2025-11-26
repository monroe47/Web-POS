from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.contrib.messages.middleware import MessageMiddleware # Import MessageMiddleware explicitly
from Account_management.middleware import SERVER_START_TOKEN # Import the actual token for comparison
from django.conf import settings # Correctly import settings here

User = get_user_model()

class AccountModelTests(TestCase):
    def test_user_creation(
        self,
    ):
        """Test that a new user can be created successfully."""
        user = User.objects.create_user(
            username='testuser',
            full_name='Test User',
            password='password123'
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'testuser')
        self.assertTrue(user.check_password('password123'))
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_superuser_creation(
        self,
    ):
        """Test that a superuser can be created successfully."""
        superuser = User.objects.create_superuser(
            username='adminuser',
            full_name='Admin User',
            password='adminpassword'
        )
        self.assertIsNotNone(superuser)
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.check_password('adminpassword'))

    def test_account_str_representation(
        self,
    ):
        """Test the string representation of an Account."""
        user = User.objects.create_user(username='testuser', full_name='Test User', password='password123')
        self.assertEqual(str(user), 'testuser (staff)')

    def test_is_staff_property(
        self,
    ):
        """Test that the is_staff property works as expected."""
        user = User.objects.create_user(username='staffuser', full_name='Staff User', password='password123', role='staff')
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)


@override_settings(MIDDLEWARE=[
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
])
class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='authuser', full_name='Auth User', password='authpassword')
        self.user.is_active = True
        self.user.save()
        self.login_url = reverse('account_management:login')
        self.logout_url = reverse('account_management:logout')

    def test_login_view(self):
        """Test successful user login."""
        response = self.client.post(self.login_url, {'username': 'authuser', 'password': 'authpassword'})
        self.assertRedirects(response, reverse('pos:dashboard'))
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_logout_view(self):
        """Test successful user logout."""
        self.client.login(username='authuser', password='authpassword')
        response = self.client.get(self.logout_url)
        self.assertRedirects(response, reverse('account_management:login'))
        self.assertFalse('_auth_user_id' in self.client.session)


@override_settings(MIDDLEWARE=[
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'Account_management.middleware.ServerRestartSessionMiddleware'
])
class MiddlewareTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='miduser', full_name='Middleware User', password='midpassword')
        self.user.is_active = True
        self.user.save() # Save the user after setting is_active

        # Use client.login() to properly establish the session and set the initial server_start_token
        # This performs a full POST request to the login view.
        login_post_response = self.client.post(reverse('account_management:login'), {'username': 'miduser', 'password': 'midpassword'}, follow=True)
        self.assertRedirects(login_post_response, reverse('pos:dashboard'), msg_prefix="Login POST failed to redirect to dashboard")
        self.client.session.load() # Reload session after login POST and redirect

        self.login_url = reverse('account_management:login')
        self.dashboard_url = reverse('pos:dashboard')

    def test_middleware_forces_relogin_on_restart(self):
        """Confirm middleware invalidates sessions after a simulated server restart."""
        # At this point, the user is already logged in from setUp and session is set
        self.assertTrue(self.client.session.get('_auth_user_id') == self.user.pk, "User not authenticated in setUp")
        self.assertEqual(self.client.session.get('server_start_token'), SERVER_START_TOKEN, "Initial SERVER_START_TOKEN not set correctly by login")

        # Step 3: Simulate a server restart by manually changing the session's token to an outdated value.
        self.client.session['server_start_token'] = 'an_outdated_or_different_token_value'
        self.client.session.save()

        # Step 4: Access a protected page again. This request should trigger the middleware's logout/redirect.
        response_after_token_mismatch = self.client.get(self.dashboard_url, follow=False)

        # Step 5: Assert the redirect to the login page
        expected_redirect_url = self.login_url + '?next=' + self.dashboard_url
        self.assertRedirects(response_after_token_mismatch, expected_redirect_url)

        # Step 6: Verify session state after the redirect
        self.client.session.load()
        self.assertFalse(self.client.session.get('_auth_user_id', False), "User should be logged out")
        self.assertIsNone(self.client.session.get('server_start_token'), "Server start token should be cleared from session")
