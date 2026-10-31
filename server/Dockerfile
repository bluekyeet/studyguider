FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY reviews.py .
COPY exams.py .
COPY lessons.py .
COPY marking.py .
COPY scheduler.py .
COPY ocr.py .
COPY worker.py .
COPY explain.py .
COPY review_generation.py .
COPY styles.py .
COPY set_password.py .
COPY manage.html .
RUN mkdir -p /data/uploads && chown nobody:nogroup /data/uploads
USER nobody
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
