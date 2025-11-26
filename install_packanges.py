import subprocess
import sys
import time

# List of packages to check/install
packages = [
    "django",
    "djangorestframework",
    "pandas",
    "joblib",
    "xgboost",
    "scikit-learn",
    "statsmodels",
    "pmdarima",
    "Pillow"
]

# File to log results
log_file = "install_log.txt"

def log(message):
    """Append message to log file and print it."""
    with open(log_file, "a") as f:
        f.write(message + "\n")
    print(message)

def is_installed(package):
    """Check if package is installed using pip show."""
    result = subprocess.run([sys.executable, "-m", "pip", "show", package],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0

def install_package(package):
    """Try to install a package using pip."""
    log(f"Trying to install '{package}'...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", package],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        log(f"'{package}' installed successfully.")
    else:
        log(f"Failed to install '{package}'.\nError: {result.stderr}")
    return result.returncode == 0

def main():
    log("=== Installation Check Started ===")
    
    for package in packages:
        attempt = 1
        while not is_installed(package):
            log(f"'{package}' is not installed. Attempt {attempt}...")
            success = install_package(package)
            if not success:
                log(f"Retrying installation for '{package}' after 5 seconds...")
                time.sleep(5)
            attempt += 1
        else:
            log(f"'{package}' is already installed or installation succeeded.")

    log("=== Installation Check Completed ===")

if __name__ == "__main__":
    main()
