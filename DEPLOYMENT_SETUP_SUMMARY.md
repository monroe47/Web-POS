# PythonAnywhere Deployment Setup - Complete Guide

## What Has Been Prepared

Your Django project has been configured for PythonAnywhere deployment. Here's what was created:

### 📋 New Files Created

1. **requirements.txt**
   - All Python dependencies for production
   - Includes: Django, ML libraries (scikit-learn, XGBoost, statsmodels), gunicorn, whitenoise
   - Ready to install on PythonAnywhere

2. **POSwithSalesForecast/settings_production.py**
   - Production-specific Django settings
   - Security configurations (SSL, CSRF protection)
   - Static files configuration with WhiteNoise
   - Logging setup
   - Ready to use: `export DJANGO_SETTINGS_MODULE=POSwithSalesForecast.settings_production`

3. **pythonanywhere_wsgi.py**
   - WSGI entry point for PythonAnywhere
   - Configured to use production settings
   - Copy this path to PythonAnywhere Web configuration

4. **deployment_checklist.py**
   - Pre-deployment verification script
   - Run locally: `python deployment_checklist.py`
   - Checks settings, dependencies, migrations, etc.

5. **setup_pythonanywhere.sh**
   - Bash script for automated setup on PythonAnywhere
   - Clone, create venv, install requirements, collect static files

6. **.gitignore**
   - Protects sensitive files from being committed
   - Includes: venv, db.sqlite3, .env, __pycache__, etc.

7. **PYTHONANYWHERE_DEPLOYMENT_GUIDE.md**
   - Step-by-step deployment instructions
   - Troubleshooting guide
   - Best practices

### 🔧 Settings Updated

**POSwithSalesForecast/settings.py** (Development)
- Now supports environment variables
- DEBUG can be controlled via `DEBUG` env var
- ALLOWED_HOSTS configurable via env
- SECRET_KEY can be overridden

---

## Quick Start: Deploy to PythonAnywhere in 5 Steps

### Step 1: Prepare Your Code
```bash
# Run deployment checklist locally
python deployment_checklist.py

# Commit and push to GitHub
git add .
git commit -m "Setup for PythonAnywhere deployment"
git push origin main
```

### Step 2: Create PythonAnywhere Account
- Go to https://www.pythonanywhere.com
- Sign up (free account available)
- Note your username

### Step 3: Upload Code
In PythonAnywhere Bash console:
```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

### Step 4: Set Up Environment
In PythonAnywhere Bash console:
```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser  # Create admin account
python manage.py collectstatic --noinput
```

### Step 5: Configure Web App
In PythonAnywhere **Web** tab:

1. **Add a new web app** → Python 3.10 → Manual configuration
2. **Set Virtualenv**: `/home/username/your-repo/venv`
3. **Edit WSGI file** and set:
   ```python
   import os
   import sys
   
   path = '/home/username/your-repo'
   sys.path.insert(0, path)
   
   os.environ['DJANGO_SETTINGS_MODULE'] = 'POSwithSalesForecast.settings_production'
   
   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
4. **Add Static Files mapping**:
   - URL: `/static/` → Directory: `/home/username/your-repo/staticfiles`
   - URL: `/media/` → Directory: `/home/username/your-repo/inventory_images`
5. **Reload** the web app

---

## Environment Variables Required

Set these in PythonAnywhere **Web** tab → Environment variables:

```
DJANGO_SECRET_KEY = (generate with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
ENVIRONMENT = production
DEBUG = False
```

---

## File Structure for PythonAnywhere

```
/home/username/your-repo/
├── venv/                              # Virtual environment
├── POSwithSalesForecast/
│   ├── settings.py                    # Development settings
│   ├── settings_production.py         # ← Production settings
│   ├── urls.py
│   ├── wsgi.py
│   └── ...
├── Inventory/
├── POS/
├── Account_management/
├── Sales_forecast/
├── Sheet/
├── pythonanywhere_wsgi.py            # ← WSGI entry point
├── manage.py
├── requirements.txt                   # ← All dependencies
├── db.sqlite3                         # Database (created after migrate)
├── staticfiles/                       # ← Collected static files
├── inventory_images/                  # ← Media files
└── ...
```

---

## Key Production Settings

### Security (settings_production.py)
- ✅ DEBUG = False
- ✅ SSL/HTTPS redirects enabled
- ✅ Secure cookies configured
- ✅ XSS protection enabled
- ✅ ALLOWED_HOSTS restricted
- ✅ WhiteNoise for static files

### Performance
- WhiteNoise middleware for efficient static file serving
- Browser cache headers configured
- Session caching enabled

### Database
- SQLite (works well for small-medium apps)
- Optional: Upgrade to MySQL for production (available on PythonAnywhere)

---

## Deployment Checklist

Before deploying:
- [ ] Run `python deployment_checklist.py` locally and fix all failures
- [ ] Test locally: `python manage.py runserver`
- [ ] Commit all changes: `git push origin main`
- [ ] Create `.env` file with sensitive data (don't commit)
- [ ] Generate new SECRET_KEY for production

During PythonAnywhere setup:
- [ ] Clone repository to PythonAnywhere
- [ ] Create virtual environment
- [ ] Install requirements.txt
- [ ] Run migrations: `python manage.py migrate`
- [ ] Create superuser: `python manage.py createsuperuser`
- [ ] Collect static files: `python manage.py collectstatic --noinput`
- [ ] Configure WSGI file
- [ ] Set environment variables
- [ ] Configure static files mapping
- [ ] Reload web app

After deployment:
- [ ] Visit https://username.pythonanywhere.com
- [ ] Test admin login at https://username.pythonanywhere.com/admin
- [ ] Check error logs in Web tab
- [ ] Test main features
- [ ] Monitor performance

---

## Common Issues & Solutions

### "Module not found" error
```bash
# Verify virtual environment
source venv/bin/activate
pip list | grep Django

# Reinstall requirements
pip install -r requirements.txt
```

### Static files not loading
```bash
# Collect static files again
python manage.py collectstatic --clear --noinput

# Verify path in Web tab matches:
# /home/username/your-repo/staticfiles
```

### Database errors
```bash
# Check database migrations
python manage.py showmigrations

# If issues, backup and reset:
cp db.sqlite3 db.sqlite3.backup
python manage.py migrate --fake-initial
```

### Long startup time
- Normal for first load (Django compilation)
- Subsequent requests will be faster
- Consider upgrading PythonAnywhere plan for faster CPU

---

## Useful PythonAnywhere Console Commands

```bash
# Activate virtual environment
source /home/username/your-repo/venv/bin/activate

# Django management commands
python manage.py shell                    # Interactive shell
python manage.py dbshell                  # Database shell
python manage.py dumpdata > backup.json   # Backup data

# Install/update packages
pip install package-name
pip install -r requirements.txt --upgrade

# View logs
tail -f /var/log/username@pythonanywhere_com_django.log
```

---

## Production Database Upgrade (Future)

When you're ready to use MySQL instead of SQLite:

1. Create MySQL database in PythonAnywhere
2. Update `settings_production.py`:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.mysql',
           'NAME': 'username$database_name',
           'USER': 'username',
           'PASSWORD': 'your-password',
           'HOST': 'username.mysql.pythonanywhere-services.com',
       }
   }
   ```
3. Migrate: `python manage.py migrate`

---

## Monitoring & Maintenance

### Regular Tasks
- [ ] Monitor error logs weekly
- [ ] Backup database monthly: `python manage.py dumpdata > backup.json`
- [ ] Update dependencies quarterly: `pip install -r requirements.txt --upgrade`
- [ ] Check server performance in PythonAnywhere dashboard

### Scaling Up
- Upgrade PythonAnywhere plan for more CPU/RAM
- Migrate to MySQL for better database performance
- Use CDN for static files (optional)

---

## Support Resources

- **PythonAnywhere Docs**: https://help.pythonanywhere.com/
- **Django Docs**: https://docs.djangoproject.com/
- **This Project's Deployment Guide**: See `PYTHONANYWHERE_DEPLOYMENT_GUIDE.md`

---

## What's Next?

1. ✅ **Done**: Project is configured for PythonAnywhere
2. ⏭️ **Next**: Run `python deployment_checklist.py` to verify everything
3. ⏭️ **Then**: Create GitHub repository and push code
4. ⏭️ **Finally**: Follow the 5-step quick start above to deploy

---

**Last Updated**: November 26, 2025  
**Django Version**: 5.2.6  
**Python Version**: 3.10+  
**Target Platform**: PythonAnywhere

---

## Questions?

Check the detailed guide: `PYTHONANYWHERE_DEPLOYMENT_GUIDE.md`  
Or refer to PythonAnywhere official documentation.
