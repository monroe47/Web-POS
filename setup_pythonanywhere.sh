#!/bin/bash
# PythonAnywhere Setup Script
# This script should be run in PythonAnywhere's Bash console
# Copy and paste the entire script into your Bash console

echo "========================================="
echo "PythonAnywhere Django Setup Script"
echo "========================================="

# Set variables (CHANGE THESE)
GITHUB_REPO="https://github.com/youruser/your-repo.git"
PROJECT_NAME="POSwithSalesandInventoryManagementwithSalesForecast"
USERNAME=$(whoami)
PYTHON_VERSION="3.10"

echo ""
echo "Step 1: Clone repository..."
cd /home/$USERNAME
git clone $GITHUB_REPO || echo "Repository already cloned or not accessible"

echo ""
echo "Step 2: Create virtual environment..."
cd /home/$USERNAME/$PROJECT_NAME
python$PYTHON_VERSION -m venv venv

echo ""
echo "Step 3: Activate virtual environment..."
source venv/bin/activate

echo ""
echo "Step 4: Upgrade pip..."
pip install --upgrade pip

echo ""
echo "Step 5: Install requirements..."
pip install -r requirements.txt

echo ""
echo "Step 6: Collect static files..."
python manage.py collectstatic --noinput

echo ""
echo "Step 7: Run migrations..."
python manage.py migrate

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Create superuser: python manage.py createsuperuser"
echo "2. Go to PythonAnywhere Web tab"
echo "3. Add new web app with Python 3.10"
echo "4. Configure WSGI file (see deployment guide)"
echo "5. Set virtualenv to: /home/$USERNAME/$PROJECT_NAME/venv"
echo "6. Configure static files mapping"
echo "7. Click Reload"
echo ""
