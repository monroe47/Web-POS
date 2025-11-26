"""
Production settings for PythonAnywhere deployment.
This extends the base settings with production-specific configurations.
"""

from .settings import *
import os

# Override debug mode - NEVER True in production
DEBUG = False

# Set your PythonAnywhere domain
# Replace 'username' with your actual PythonAnywhere username
ALLOWED_HOSTS = [
    'username.pythonanywhere.com',  # Replace with your actual domain
    'www.username.pythonanywhere.com',
    '127.0.0.1',
    'localhost',
]

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_SECURITY_POLICY = {
    "default-src": ("'self'",),
}

# Secret key - Use environment variable in production
# This should be set in PythonAnywhere Web tab under Environment variables
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'change-me-in-production')

# Database - Consider using MySQL on PythonAnywhere for production
# For now keeping SQLite, but you can upgrade to MySQL later
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'inventory_images')

# Whitenoise configuration for serving static files efficiently
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Optional: Enable compression for WhiteNoise
WHITENOISE_COMPRESS = True
WHITENOISE_MIMETYPES = {
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
}

# Logging configuration for production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file', 'console'],
        'level': 'INFO',
    },
}

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Cache configuration (optional, helps with performance)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'pos-cache',
    }
}

# Email configuration - Configure for production emails
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'  # or your email service
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
# EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')

# Session timeout
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Allowed file extensions for uploads
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

# Time zone
TIME_ZONE = 'Asia/Manila'
USE_TZ = True

print("✓ Production settings loaded")
