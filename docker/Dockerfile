FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV FLASK_APP=app.py APP_ENV=production
# Không chạy root: một lỗ RCE trong app không chiếm trọn container
RUN useradd --create-home --uid 1001 app && chown -R app:app /app
USER app
EXPOSE 8000
# Migration KHÔNG chạy ở đây — service `migrate` one-shot đảm nhiệm (chống race)
CMD ["gunicorn", "-c", "docker/gunicorn.conf.py", "app:app"]
