FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV FLASK_APP=app.py FLASK_CONFIG=production
EXPOSE 8000
CMD ["sh", "-c", "flask db upgrade && flask seed-admin && gunicorn -b 0.0.0.0:8000 -w 2 app:app"]
