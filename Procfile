web: FLASK_ENV=production gunicorn --worker-class gthread -w 1 --threads 32 --bind "0.0.0.0:${PORT:-5000}" --timeout 120 wsgi:app
