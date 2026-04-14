import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_api.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

# Delete all users that are not 'dane' to remove insecure generic accounts
deleted_count = 0
for u in User.objects.exclude(username='dane'):
    u.delete()
    deleted_count += 1

print(f"Deleted {deleted_count} generic/insecure users.")

# Create or update the core admin user from .env
admin, created = User.objects.get_or_create(username='dane')
admin.set_password('DADZe22lda1!')
admin.is_staff = True
admin.is_superuser = True
admin.save()

verb = "Created" if created else "Updated"
print(f"{verb} SECURE superuser 'dane' with encrypted .env credentials successfully!")
