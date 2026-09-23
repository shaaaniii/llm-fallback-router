# Slim Python base — this app has no compiled dependencies that need a full image.
FROM python:3.12-slim

WORKDIR /app

# Copy requirements first so Docker caches this layer — it only
# re-installs packages when requirements.txt itself changes, not on
# every code edit.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

EXPOSE 8000

# --proxy-headers: trust X-Forwarded-* from the reverse proxy in front of
# this container (docker-compose, or a real load balancer in production).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]