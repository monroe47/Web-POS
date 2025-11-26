from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Account, UserLog

# -----------------------------------
# Custom User Admin (for Account model)
# -----------------------------------
@admin.register(Account)
class CustomAccountAdmin(UserAdmin):
    model = Account
    list_display = ('username', 'first_name', 'last_name', 'role', 'is_staff', 'is_superuser', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'first_name', 'last_name')
    ordering = ('username',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'password1', 'password2',
                'first_name', 'last_name', 'role',
                'is_staff', 'is_superuser'
            ),
        }),
    )


# -----------------------------------
# User Log Admin (editable and deletable by admins)
# -----------------------------------
@admin.register(UserLog)
class UserLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'description', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username', 'description')
    ordering = ('-timestamp',)

    # Allow editing and deleting in admin (default behavior)
    # If you want certain fields immutable in the admin, add them to readonly_fields.
    # Example: readonly_fields = ('timestamp',)

    # Audit admin edits to UserLog: record which admin edited the log
    def save_model(self, request, obj, form, change):
        """
        Called when an admin creates or updates a UserLog in the admin.
        We append a short audit note to description and then save.
        """
        if change:
            # preserve original description and append editor info
            editor = request.user.username
            audit_note = f"\n[Edited by admin: {editor} at {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}]"
            # only append once to avoid repeated notes on repeated saves in the same session
            if audit_note not in (obj.description or ""):
                obj.description = (obj.description or "") + audit_note
        super().save_model(request, obj, form, change)

    # Audit admin deletions of UserLog: create a separate log entry recording who deleted it
    def delete_model(self, request, obj):
        """
        Called when an admin deletes a UserLog in the admin.
        We create a preservation log entry to record the deletion action.
        """
        deleter = request.user
        # create an audit record (use the same UserLog model to track the deletion)
        UserLog.objects.create(
            user=deleter,
            action='delete',
            description=f"Admin '{deleter.username}' deleted UserLog for user '{obj.user.username}' (action was '{obj.action}'; original timestamp: {obj.timestamp.strftime('%Y-%m-%d %H:%M:%S')})"
        )
        super().delete_model(request, obj)

    # Optionally log bulk deletions from the changelist (admin action)
    def delete_queryset(self, request, queryset):
        deleter = request.user
        for obj in queryset:
            UserLog.objects.create(
                user=deleter,
                action='delete',
                description=f"Admin '{deleter.username}' bulk-deleted UserLog for user '{obj.user.username}' (action was '{obj.action}'; original timestamp: {obj.timestamp.strftime('%Y-%m-%d %H:%M:%S')})"
            )
        super().delete_queryset(request, queryset)
