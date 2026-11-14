FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /srv

# Dependencies first: this layer stays cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home appuser
COPY . .
# Static files for the admin and the browsable API, served by WhiteNoise.
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput
USER appuser

EXPOSE 8000
# Apply migrations and seed on every start (both are no-ops when already done), then serve.
CMD ["sh", "-c", "python manage.py migrate --noinput && if [ \"$SEED_DEMO_DATA\" = true ]; then python manage.py seed; fi && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2"]
