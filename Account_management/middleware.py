from datetime import datetime
import uuid

from django.contrib.auth import logout as django_logout
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages

# Token that changes each process start. When the server restarts, this value changes,
# allowing us to detect that existing sessions were created before the restart.
SERVER_START_TOKEN = uuid.uuid4().hex
SERVER_START_TIME = datetime.utcnow()

class ServerRestartSessionMiddleware:
    """Middleware that forces users to re-authenticate after a server restart.

    Behavior:
    - On each request, if the user is authenticated and the session contains a
      `server_start_token` value that does not match the current `SERVER_START_TOKEN`,
      they will be logged out and redirected to the login page.
    - We do not force logout for sessions that do not contain the token (likely
      created before this middleware was deployed). The token is written at login.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Allow login and static/media endpoints to run without forcing a redirect
        login_path = reverse('account_management:login')
        # Normalize path (without querystring)
        current_path = request.path

        # Only enforce for authenticated users and when not already on the login page
        if request.user.is_authenticated and current_path != login_path:
            session_token = request.session.get('server_start_token')
            # Only force logout if the session explicitly contains a token and it differs
            if session_token is not None and session_token != SERVER_START_TOKEN:
                # Invalidate session and log out
                try:
                    django_logout(request)
                except Exception:
                    # best-effort logout
                    pass
                # Clear session data to avoid leaking stale data
                try:
                    request.session.flush()
                except Exception:
                    pass
                # Add an informational message if message middleware is installed
                try:
                    messages.info(request, 'Server restarted - please log in again to continue.')
                except Exception:
                    pass
                # Redirect to login page
                return redirect(login_path)

        response = self.get_response(request)
        return response
