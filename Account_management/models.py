from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone

# ------------------------------
# Custom Account Manager
# ------------------------------
class AccountManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, email=None, full_name='', password=None, role='staff', **extra_fields):
        if not username:
            raise ValueError("Username is required")
        email = self.normalize_email(email)
        username_clean = username.lower()
        user = self.model(
            username=username_clean,
            email=email,
            full_name=full_name,
            role=(role or 'staff').lower(),
            **extra_fields,
        )
        user.set_password(password)
        # By default, created users are staff in this app
        user.is_staff = extra_fields.get('is_staff', True)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, full_name='', password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, email=email, full_name=full_name, password=password, role='admin', **extra_fields)


# ------------------------------
# Custom Account Model
# ------------------------------
class Account(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('staff', 'Staff'),
    ]

    full_name = models.CharField(max_length=255, blank=True)  # Add this field
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='staff')

    objects = AccountManager()  # Custom manager

    def __str__(self):
        return f"{self.username} ({self.role})"


# ------------------------------
# User Log Model
# ------------------------------
from django.utils import timezone
from datetime import timedelta

class UserLog(models.Model):
    ACTION_CHOICES = [
        ('login', 'User logged in'),
        ('logout', 'User logged out'),
        ('add', 'Added record'),
        ('edit', 'Edited record'),
        ('delete', 'Deleted record'),
        ('restock', 'Restocked inventory'),
        ('pos_sale', 'POS sale transaction'),
        ('pos', 'POS transaction'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey('Account', on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} ({self.timestamp.strftime('%Y-%m-%d %H:%M:%S')})"

    @classmethod
    def delete_old_logs(cls):
        one_month_ago = timezone.now() - timedelta(days=30)
        cls.objects.filter(timestamp__lt=one_month_ago).delete()