"""
PythonAnywhere Pre-Deployment Checklist

This script verifies that your Django project is ready for PythonAnywhere deployment.
Run this before uploading to production.

Usage:
    python deployment_checklist.py
"""

import os
import sys
import django
from pathlib import Path
from django.core.management import execute_from_command_line

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'POSwithSalesForecast.settings_production')
django.setup()

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
CHECKMARK = '✓'
XMARK = '✗'

class DeploymentChecker:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def print_header(self, title):
        print(f"\n{BLUE}{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}{RESET}")
    
    def check_pass(self, name, message=""):
        self.passed += 1
        msg = f"{GREEN}{CHECKMARK}{RESET} {name}"
        if message:
            msg += f" - {message}"
        print(msg)
    
    def check_fail(self, name, message=""):
        self.failed += 1
        msg = f"{RED}{XMARK}{RESET} {name}"
        if message:
            msg += f" - {message}"
        print(msg)
    
    def check_warn(self, name, message=""):
        self.warnings += 1
        msg = f"{YELLOW}⚠{RESET} {name}"
        if message:
            msg += f" - {message}"
        print(msg)
    
    def check_requirements(self):
        self.print_header("1. CHECKING REQUIREMENTS FILE")
        
        req_file = self.base_dir / 'requirements.txt'
        if req_file.exists():
            self.check_pass("requirements.txt", "Found")
            with open(req_file) as f:
                packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            print(f"  → {len(packages)} packages listed")
            
            required = ['Django', 'djangorestframework', 'pandas', 'gunicorn', 'whitenoise']
            for pkg in required:
                if any(pkg.lower() in p.lower() for p in packages):
                    self.check_pass(f"  Required: {pkg}")
                else:
                    self.check_fail(f"  Required: {pkg}", "Missing from requirements.txt")
        else:
            self.check_fail("requirements.txt", "Not found")
    
    def check_settings(self):
        self.print_header("2. CHECKING SETTINGS FILES")
        
        # Check main settings
        main_settings = self.base_dir / 'POSwithSalesForecast' / 'settings.py'
        if main_settings.exists():
            self.check_pass("settings.py", "Found")
        else:
            self.check_fail("settings.py", "Not found")
        
        # Check production settings
        prod_settings = self.base_dir / 'POSwithSalesForecast' / 'settings_production.py'
        if prod_settings.exists():
            self.check_pass("settings_production.py", "Found for production")
        else:
            self.check_fail("settings_production.py", "Not found - needed for production")
    
    def check_wsgi(self):
        self.print_header("3. CHECKING WSGI CONFIGURATION")
        
        wsgi = self.base_dir / 'pythonanywhere_wsgi.py'
        if wsgi.exists():
            self.check_pass("pythonanywhere_wsgi.py", "Found")
        else:
            self.check_warn("pythonanywhere_wsgi.py", "Create this file on PythonAnywhere")
    
    def check_django_setup(self):
        self.print_header("4. CHECKING DJANGO SETUP")
        
        try:
            from django.conf import settings
            
            # Check DEBUG
            if not settings.DEBUG:
                self.check_pass("DEBUG Mode", "Set to False for production")
            else:
                self.check_warn("DEBUG Mode", "Currently True - will be False in production")
            
            # Check ALLOWED_HOSTS
            if settings.ALLOWED_HOSTS:
                self.check_pass("ALLOWED_HOSTS", f"Configured: {settings.ALLOWED_HOSTS}")
            else:
                self.check_warn("ALLOWED_HOSTS", "Empty - configure before deployment")
            
            # Check SECRET_KEY
            if settings.SECRET_KEY and 'insecure' not in settings.SECRET_KEY.lower():
                self.check_pass("SECRET_KEY", "Custom key configured")
            else:
                self.check_warn("SECRET_KEY", "Using default/insecure key - change before deployment")
            
            # Check installed apps
            required_apps = ['django.contrib.staticfiles', 'Inventory', 'POS', 'Account_management']
            missing = []
            for app in required_apps:
                if app not in settings.INSTALLED_APPS:
                    missing.append(app)
            
            if not missing:
                self.check_pass("INSTALLED_APPS", "All required apps configured")
            else:
                self.check_fail("INSTALLED_APPS", f"Missing: {', '.join(missing)}")
            
            # Check database
            if settings.DATABASES['default']['ENGINE']:
                self.check_pass("Database", f"{settings.DATABASES['default']['ENGINE']}")
            else:
                self.check_fail("Database", "Not configured")
            
            # Check static files
            if settings.STATIC_ROOT:
                self.check_pass("STATIC_ROOT", f"{settings.STATIC_ROOT}")
            else:
                self.check_fail("STATIC_ROOT", "Not configured")
            
        except Exception as e:
            self.check_fail("Django Configuration", str(e))
    
    def check_static_media(self):
        self.print_header("5. CHECKING STATIC & MEDIA DIRECTORIES")
        
        static = self.base_dir / 'static'
        staticfiles = self.base_dir / 'staticfiles'
        media = self.base_dir / 'inventory_images'
        
        if static.exists():
            self.check_pass("static/", "Directory exists")
        else:
            self.check_warn("static/", "Directory not found - create if needed")
        
        if media.exists():
            self.check_pass("inventory_images/", "Media directory exists")
        else:
            self.check_warn("inventory_images/", "Will be created on PythonAnywhere")
    
    def check_migrations(self):
        self.print_header("6. CHECKING DATABASE MIGRATIONS")
        
        apps = ['Inventory', 'POS', 'Account_management', 'Sales_forecast', 'Sheet']
        
        for app in apps:
            migrations_dir = self.base_dir / app / 'migrations'
            if migrations_dir.exists():
                migration_files = list(migrations_dir.glob('*.py'))
                if len(migration_files) > 1:
                    self.check_pass(f"{app}/migrations/", f"{len(migration_files)} files")
                else:
                    self.check_warn(f"{app}/migrations/", "Only __init__.py found")
            else:
                self.check_warn(f"{app}/migrations/", "Directory not found")
    
    def check_git(self):
        self.print_header("7. CHECKING GIT REPOSITORY")
        
        git_dir = self.base_dir / '.git'
        gitignore = self.base_dir / '.gitignore'
        
        if git_dir.exists():
            self.check_pass(".git/", "Repository initialized")
        else:
            self.check_warn(".git/", "Not initialized - recommended for easy deployment")
        
        if gitignore.exists():
            self.check_pass(".gitignore", "File exists")
        else:
            self.check_warn(".gitignore", "File not found - will be created")
    
    def check_documentation(self):
        self.print_header("8. CHECKING DOCUMENTATION")
        
        deploy_guide = self.base_dir / 'PYTHONANYWHERE_DEPLOYMENT_GUIDE.md'
        if deploy_guide.exists():
            self.check_pass("Deployment Guide", "PYTHONANYWHERE_DEPLOYMENT_GUIDE.md found")
        else:
            self.check_warn("Deployment Guide", "Not found")
    
    def print_summary(self):
        self.print_header("DEPLOYMENT CHECKLIST SUMMARY")
        
        total = self.passed + self.failed + self.warnings
        print(f"\n{GREEN}✓ Passed: {self.passed}{RESET}")
        if self.failed > 0:
            print(f"{RED}✗ Failed: {self.failed}{RESET}")
        if self.warnings > 0:
            print(f"{YELLOW}⚠ Warnings: {self.warnings}{RESET}")
        
        print(f"\nTotal Checks: {total}")
        
        if self.failed == 0:
            print(f"\n{GREEN}✓ Ready for deployment!{RESET}")
            return True
        else:
            print(f"\n{RED}✗ Fix failures before deploying{RESET}")
            return False
    
    def run_all_checks(self):
        self.print_header("DJANGO PROJECT DEPLOYMENT CHECKER")
        print(f"Project: {self.base_dir.name}")
        print(f"Environment: PythonAnywhere")
        
        self.check_requirements()
        self.check_settings()
        self.check_wsgi()
        self.check_django_setup()
        self.check_static_media()
        self.check_migrations()
        self.check_git()
        self.check_documentation()
        
        return self.print_summary()

if __name__ == '__main__':
    checker = DeploymentChecker()
    success = checker.run_all_checks()
    sys.exit(0 if success else 1)
