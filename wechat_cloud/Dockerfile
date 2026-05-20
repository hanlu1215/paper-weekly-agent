FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=wxcloudrun.settings

EXPOSE 80

CMD ["gunicorn", "wxcloudrun.wsgi:application", "--bind", "0.0.0.0:80", "--workers", "2", "--timeout", "120"]
