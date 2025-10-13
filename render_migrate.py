# render_migrate.py
import os
import sys

# Ensure project root is in path (only necessary in some setups)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "epts_backend.settings")

# Run Django setup
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

# Run management commands
from django.core.management import call_command

print("Running migrations...")
call_command("migrate", interactive=False)
print("Collecting static files...")
call_command("collectstatic", "--noinput")
print("Migrations and collectstatic completed.")
