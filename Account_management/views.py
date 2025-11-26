from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
import csv
from .models import UserLog, Account
from zoneinfo import ZoneInfo

# Import server restart token so we can persist it into the session at login
from .middleware import SERVER_START_TOKEN

User = get_user_model()


# -------------------------
# Utilities
# -------------------------
def is_admin(user):
    return bool(user and (user.is_superuser or getattr(user, "role", "").lower() == "admin"))


def log_action(user, action, description=""):
    UserLog.objects.create(user=user, action=action, description=description)


# -------------------------
# Authentication
# -------------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect("pos:dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        if not username or not password:
            messages.error(request, "Both username and password are required.")
        else:
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                # Persist the server start token in the session so middleware can validate
                try:
                    request.session['server_start_token'] = SERVER_START_TOKEN
                except Exception:
                    # if session isn't available for some reason, ignore – user is still logged in
                    pass
                log_action(user, "login", "User logged in")
                messages.success(request, f"Welcome back, {getattr(user, 'full_name', user.username)}!")
                return redirect("pos:dashboard")
            messages.error(request, "Invalid username or password.")

    return render(request, "account_management/login.html") # Corrected template path


@login_required
def logout_view(request):
    log_action(request.user, "logout", "User logged out")
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("account_management:login")


# -------------------------
# Account Management
# -------------------------
@login_required
@user_passes_test(is_admin)
def account_list(request):
    q = request.GET.get("q", "").strip()
    accounts = User.objects.all()
    if q:
        accounts = accounts.filter(full_name__icontains=q) | accounts.filter(username__icontains=q)
    accounts = accounts.order_by("username")
    return render(request, "Account_management/account_management.html", {"accounts": accounts})


@login_required
@user_passes_test(is_admin)
def create_account(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        username = request.POST.get("username", "").strip().lower()
        password = request.POST.get("password", "").strip()
        role = request.POST.get("role", "staff").strip().lower()

        if not (full_name and username and password):
            messages.error(request, "All fields are required.")
            return redirect("account_management:account_list")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("account_management:account_list")

        user = User.objects.create_user(username=username, full_name=full_name, password=password, role=role)
        user.is_staff = True
        if role == "admin":
            user.is_superuser = True
        user.save()

        # Assign to group
        group, _ = Group.objects.get_or_create(name=role.capitalize())
        user.groups.add(group)

        log_action(request.user, "add", f"Created account: {username}")
        messages.success(request, f"Account for {full_name} ({role.capitalize()}) created successfully.")

    return redirect("account_management:account_list")


@login_required
@user_passes_test(is_admin)
def delete_account(request, user_id):
    """
    AJAX-based account delete function.
    Deletes a user and returns JSON instead of redirect.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

    target = get_object_or_404(User, pk=user_id)

    # Prevent self-deletion
    if target.pk == request.user.pk:
        return JsonResponse({"success": False, "message": "You cannot delete your own account."}, status=403)

    username = target.username
    try:
        target.delete()
        log_action(request.user, "delete", f"Deleted account: {username}")
        return JsonResponse({
            "success": True,
            "message": f"Account '{username}' deleted successfully."
        })
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": f"An error occurred: {str(e)}"
        }, status=500)


# -------------------------
# User Logs / AJAX
# -------------------------
@login_required
@user_passes_test(is_admin)
def user_logs(request, user_id):
    selected_user = get_object_or_404(User, pk=user_id)
    logs = UserLog.objects.filter(user=selected_user).order_by("-timestamp")[:20]

    if request.headers.get("x-requested-with", "").lower() == "xmlhttprequest":
        manila_tz = ZoneInfo("Asia/Manila")
        return JsonResponse({
            "logs": [
                {
                    "action_display": log.get_action_display(),
                    "description": log.description,
                    "timestamp": timezone.localtime(log.timestamp, manila_tz).strftime("%b %d, %Y %I:%M %p"),
                }
                for log in logs
            ]
        })

    accounts = User.objects.all().order_by("username")
    return render(request, "Account_management/account_management.html", {
        "accounts": accounts,
        "logs": logs,
        "selected_user": selected_user
    })


# -------------------------
# Export Accounts CSV
# -------------------------
@login_required
@user_passes_test(is_admin)
def export_accounts_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="accounts.csv"'

    writer = csv.writer(response)
    writer.writerow(["Full Name", "Username", "Role", "Date Joined", "Last Login"])

    manila_tz = ZoneInfo("Asia/Manila")
    for u in User.objects.all().order_by("username"):
        date_joined = timezone.localtime(u.date_joined, manila_tz).strftime("%Y-%m-%d") if getattr(u, "date_joined", None) else ""
        last_login = timezone.localtime(u.last_login, manila_tz).strftime("%Y-%m-%d %I:%M %p") if getattr(u, "last_login", None) else "Never"
        writer.writerow([
            getattr(u, "full_name", ""),
            u.username,
            getattr(u, "role", "staff").capitalize(),
            date_joined,
            last_login,
        ])
    return response