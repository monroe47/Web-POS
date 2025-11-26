# PythonAnywhere Deployment Guide

This guide walks you through deploying the POS with Sales Forecast system on PythonAnywhere.

## Step 1: Prepare Your Local Project

### 1.1 Generate Requirements File (Already Done)
The `requirements.txt` file is already created with all necessary dependencies:
- Django 5.2.6
- Django REST Framework
- Pandas, NumPy (Data processing)
- scikit-learn, XGBoost, statsmodels (ML/forecasting)
- Gunicorn (Production server)
- WhiteNoise (Static files)

### 1.2 Test Requirements
```bash
pip install -r requirements.txt
python manage.py test
```

---

## Step 2: Set Up PythonAnywhere Account

1. Go to [www.pythonanywhere.com](https://www.pythonanywhere.com)
2. Sign up for a free or paid account
3. Note your username (you'll use it frequently)

---

## Step 3: Upload Code to PythonAnywhere

### Option A: Using Git (Recommended)
1. Push your project to GitHub/GitLab
2. In PythonAnywhere Bash console:
   ```bash
   git clone https://github.com/yourusername/your-repo.git
   cd your-repo
   ```

### Option B: Using Web Upload
1. In PythonAnywhere, go to **Files**
2. Upload your project files

### Option C: Using Web App Clone (Easiest)
1. Go to **Web** tab → **Add a new web app**
2. Choose "Clone an existing web app" or manual setup

---

## Step 4: Create Virtual Environment on PythonAnywhere

In PythonAnywhere **Bash** console:

```bash
# Navigate to your project directory
cd /home/username/POSwithSalesandInventoryManagementwithSalesForecast

# Create virtual environment
mkvirtualenv --python=/usr/bin/python3.10 posapp
# or
python3.10 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install requirements
pip install --upgrade pip
pip install -r requirements.txt

# Or individually:
pip install Django==5.2.6
pip install djangorestframework pandas numpy openpyxl scikit-learn statsmodels pmdarima xgboost joblib gunicorn whitenoise
```

---

## Step 5: Configure Web App in PythonAnywhere

1. Go to **Web** tab
2. Click **Add a new web app**
3. Choose **Manual configuration** → **Python 3.10**
4. After creation, configure:

### 5.1 WSGI Configuration

In the **Web** tab under "WSGI configuration file", copy this template and save:

```python
# Edit the file at /var/www/username_pythonanywhere_com_wsgi.py

import os
import sys

project_folder = '/home/username/POSwithSalesandInventoryManagementwithSalesForecast'
sys.path.insert(0, project_folder)

os.environ['DJANGO_SETTINGS_MODULE'] = 'POSwithSalesForecast.settings_production'

# Use the provided pythonanywhere_wsgi.py
from pythonanywhere_wsgi import application
```

### 5.2 Virtualenv Configuration

In the **Web** tab under "Virtualenv", set:
```
/home/username/.virtualenvs/posapp
```
(Or path to your venv if different)

### 5.3 Static Files Configuration

In the **Web** tab under "Static files", add:

| URL | Directory |
|-----|-----------|
| /static/ | /home/username/POSwithSalesandInventoryManagementwithSalesForecast/staticfiles |
| /media/ | /home/username/POSwithSalesandInventoryManagementwithSalesForecast/inventory_images |

---

## Step 6: Collect Static Files

In PythonAnywhere **Bash** console:

```bash
cd /home/username/POSwithSalesandInventoryManagementwithSalesForecast
source venv/bin/activate  # or workon posapp

# Collect static files
python manage.py collectstatic --noinput
```

---

## Step 7: Database Migration

In PythonAnywhere **Bash** console:

```bash
cd /home/username/POSwithSalesandInventoryManagementwithSalesForecast
source venv/bin/activate

# Run migrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser
# Username: admin
# Email: your@email.com
# Password: (create secure password)
```

---

## Step 8: Update Settings for Your Domain

Edit `POSwithSalesForecast/settings_production.py`:

```python
ALLOWED_HOSTS = [
    'yourusername.pythonanywhere.com',
    'www.yourusername.pythonanywhere.com',
]

# Update SECRET_KEY in Web Environment Variables
```

---

## Step 9: Set Environment Variables

In PythonAnywhere **Web** tab, scroll to "Environment variables" and add:

```
DJANGO_SECRET_KEY = (your secure random key)
ENVIRONMENT = production
```

Generate a secure key:
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

---

## Step 10: Reload Web App

In PythonAnywhere **Web** tab, click **Reload** button (green button at top).

---

## Step 11: Test Your Deployment

1. Visit `https://yourusername.pythonanywhere.com`
2. Test login at `/admin`
3. Check error logs in **Web** tab if issues occur

---

## Troubleshooting

### Error: ModuleNotFoundError
**Solution**: 
- Verify virtualenv is set correctly in Web tab
- Ensure requirements.txt is installed: `pip install -r requirements.txt`
- Check PYTHONPATH in WSGI file

### Error: Static files not loading
**Solution**:
```bash
python manage.py collectstatic --clear --noinput
```

### Error: Database locked
**Solution**:
```bash
# Restart the web app in PythonAnywhere Web tab
# Or access it via Django shell:
python manage.py dbshell
```

### Error: Media files not uploading
**Solution**:
- Ensure `inventory_images` directory exists and is writable
- Create directory if needed: `mkdir inventory_images`
- Check permissions: `chmod 755 inventory_images`

---

## Maintenance

### Regular Updates
```bash
# Update code from Git
git pull origin main

# Update Python packages
pip install --upgrade -r requirements.txt

# Restart app
# Go to Web tab and click Reload
```

### Database Backups
1. Download `db.sqlite3` from PythonAnywhere **Files**
2. Or use: `python manage.py dumpdata > backup.json`

### Logs
View application logs in **Web** tab under "Log files" section.

---

## Production Checklist

- [ ] DEBUG = False in settings_production.py
- [ ] ALLOWED_HOSTS configured correctly
- [ ] SECRET_KEY set as environment variable
- [ ] Static files collected and serving correctly
- [ ] Database migrated and seeded
- [ ] Superuser created
- [ ] SSL/HTTPS enabled (PythonAnywhere provides this)
- [ ] Email configuration updated if needed
- [ ] Backups scheduled
- [ ] Web app tested and accessible

---

## Next Steps

### Database Upgrade (Optional)
SQLite works fine for small apps. For higher traffic:
1. Upgrade PythonAnywhere account for MySQL access
2. Create MySQL database in PythonAnywhere
3. Update DATABASES in settings_production.py
4. Run migrations

### CDN & Caching (Advanced)
- Use Cloudflare for caching
- Configure caching headers in Django
- Use browser cache

### Monitoring
- Set up error alerts
- Monitor logs regularly
- Track performance metrics

---

## Support
- PythonAnywhere Documentation: https://help.pythonanywhere.com/
- Django Documentation: https://docs.djangoproject.com/
- Stack Overflow: Tag with `pythonanywhere` and `django`

