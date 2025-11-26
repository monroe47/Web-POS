# PythonAnywhere Deployment - Quick Reference Card

## 🚀 5-Minute Deployment Checklist

### Before You Deploy
```bash
# 1. Verify everything locally
python deployment_checklist.py

# 2. Test the app
python manage.py runserver

# 3. Commit & push
git add .
git commit -m "Ready for PythonAnywhere"
git push origin main
```

### On PythonAnywhere
```bash
# Terminal: Clone repo
git clone YOUR_GITHUB_URL
cd POSwithSalesandInventoryManagementwithSalesForecast

# Create & activate venv
python3.10 -m venv venv
source venv/bin/activate

# Install & setup
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

### In Web Configuration
1. **Virtualenv**: `/home/username/POSwithSalesandInventoryManagementwithSalesForecast/venv`
2. **WSGI file**: Update with provided configuration
3. **Static files**:
   - URL: `/static/` → Dir: `/home/.../staticfiles`
   - URL: `/media/` → Dir: `/home/.../inventory_images`
4. **Environment variables**:
   - `DJANGO_SECRET_KEY` = (generate new)
   - `DEBUG` = False
5. **Reload** ✅

---

## 📁 Important Files

| File | Purpose | On PythonAnywhere |
|------|---------|------------------|
| `requirements.txt` | Dependencies | Install: `pip install -r requirements.txt` |
| `settings_production.py` | Production config | Auto-loaded via env var |
| `pythonanywhere_wsgi.py` | WSGI entry point | Reference for Web config |
| `manage.py` | Django CLI | Run migrations: `python manage.py migrate` |
| `db.sqlite3` | Database | Auto-created after migration |
| `staticfiles/` | Static files | Auto-created: `collectstatic` |

---

## 🔑 Environment Variables

```bash
# Set in PythonAnywhere Web tab → Environment variables

# Generate new secret:
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Then set:
DJANGO_SECRET_KEY=<generated-key-here>
DEBUG=False
ENVIRONMENT=production
```

---

## 🐛 Quick Troubleshooting

| Issue | Fix |
|-------|-----|
| 500 error | Check logs in Web tab |
| Static files missing | `python manage.py collectstatic --clear --noinput` |
| Import errors | `pip install -r requirements.txt` in activated venv |
| Database locked | Reload web app in Web tab |
| Permission denied | `chmod 755 inventory_images/` |

---

## 📊 Project Stats

- **Apps**: Inventory, POS, Account_management, Sales_forecast, Sheet
- **Dependencies**: 15+ packages (Django, ML libs, gunicorn, whitenoise)
- **Database**: SQLite (easily upgradable to MySQL)
- **Static Files**: CSS, JS in `/static/`, collected to `/staticfiles/`
- **Media**: Product images in `/inventory_images/`

---

## 🎯 Success Indicators

After deploying, verify:
- ✅ https://username.pythonanywhere.com loads
- ✅ /admin page accessible and login works
- ✅ Static files load (CSS/JS styled correctly)
- ✅ Images/media display properly
- ✅ No errors in Web tab logs

---

## 📖 Full Guides

- **Detailed Setup**: `PYTHONANYWHERE_DEPLOYMENT_GUIDE.md`
- **Setup Summary**: `DEPLOYMENT_SETUP_SUMMARY.md`
- **Automated Checker**: Run `python deployment_checklist.py`

---

## ⚡ Common Commands

```bash
# Inside PythonAnywhere bash with venv activated:

# Manage Django
python manage.py migrate              # Apply migrations
python manage.py createsuperuser      # Create admin
python manage.py collectstatic        # Collect static files
python manage.py shell                # Django shell

# Database
python manage.py dumpdata > backup.json   # Backup
python manage.py loaddata backup.json     # Restore

# Debugging
python manage.py check                # Check config
python manage.py test                 # Run tests
```

---

## 🔒 Security Checklist

- [ ] DEBUG = False
- [ ] SECRET_KEY changed
- [ ] ALLOWED_HOSTS configured
- [ ] HTTPS enabled (automatic on PythonAnywhere)
- [ ] Superuser password strong
- [ ] db.sqlite3 not in version control
- [ ] .env secrets not committed

---

## 📱 Access Your App

| URL | Purpose |
|-----|---------|
| https://username.pythonanywhere.com | Main app |
| https://username.pythonanywhere.com/admin | Admin panel |
| https://username.pythonanywhere.com/static/ | Static files |
| https://username.pythonanywhere.com/media/ | Media/images |

---

## 🆘 Emergency Reset

If something breaks:

```bash
# 1. Reload web app (first attempt)
# In Web tab → click Reload

# 2. Check logs
# In Web tab → Log files section

# 3. Revert code
git revert HEAD

# 4. Restart web app
# In Web tab → Reload

# 5. Contact support
# PythonAnywhere: help.pythonanywhere.com
```

---

**Last Updated**: November 26, 2025  
**Platform**: PythonAnywhere  
**Django**: 5.2.6

