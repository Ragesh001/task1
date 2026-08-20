"""
WSGI config for Task1 project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Task1.settings')

application = get_wsgi_application()

# Auto-run migrations on Vercel (database lives in /tmp and resets on cold start)
if os.environ.get('DEBUG', 'False') != 'True':
    try:
        from django.core.management import call_command
        call_command('migrate', '--run-syncdb', verbosity=0)
    except Exception:
        pass
