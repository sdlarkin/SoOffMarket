import subprocess
import os

def setup_backend():
    backend_dir = "backend"
    if not os.path.exists(backend_dir):
        os.makedirs(backend_dir)
    
    # Check if django is already there
    if not os.path.exists(os.path.join(backend_dir, "manage.py")):
        print("Initializing Django project...")
        subprocess.run(["pip", "install", "django", "djangorestframework", "django-cors-headers", "python-decouple"], check=True)
        # Use --skip-checks to avoid issues during init if some envs are missing
        subprocess.run(["django-admin", "startproject", "backend_api", "."], cwd=backend_dir, check=True, shell=True)
        
        # Rename project folder to something more specific if needed, but the current script uses "."
        # Let's fix settings.py for CORS and Decouple
        settings_path = os.path.join(backend_dir, "backend_api", "settings.py")
        if os.path.exists(settings_path):
            with open(settings_path, "r") as f:
                content = f.read()
            
            # Add imports
            if "from decouple import config" not in content:
                content = "from decouple import config\n" + content
            
            # Replace SECRET_KEY
            content = content.replace("SECRET_KEY = 'django-insecure-", "SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-")
            
            # Add CORS to INSTALLED_APPS
            if "'corsheaders'," not in content:
                content = content.replace("INSTALLED_APPS = [", "INSTALLED_APPS = [\n    'corsheaders',")
            
            # Add CORS to MIDDLEWARE
            if "'corsheaders.middleware.CorsMiddleware'," not in content:
                content = content.replace("MIDDLEWARE = [", "MIDDLEWARE = [\n    'corsheaders.middleware.CorsMiddleware',")
            
            # Allow all origins for dev
            if "CORS_ALLOW_ALL_ORIGINS" not in content:
                content += "\nCORS_ALLOW_ALL_ORIGINS = True\n"
            
            with open(settings_path, "w") as f:
                f.write(content)

        apps = ["decisions", "waitlist"]
        for app in apps:
            print(f"Creating app: {app}")
            subprocess.run(["python", "manage.py", "startapp", app], cwd=backend_dir, check=True, shell=True)
            
            # Add app to INSTALLED_APPS in settings.py
            with open(settings_path, "r") as f:
                content = f.read()
            if f"'{app}'," not in content:
                content = content.replace("INSTALLED_APPS = [", f"INSTALLED_APPS = [\n    '{app}',")
            with open(settings_path, "w") as f:
                f.write(content)
    else:
        print("Backend already initialized.")

if __name__ == "__main__":
    setup_backend()
