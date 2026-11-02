FROM python:3.13-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr libcairo2 nodejs \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY reviews.py .
COPY exams.py .
COPY lessons.py .
COPY marking.py .
COPY parsing.py .
COPY usage.py .
COPY diagrams.py .
COPY scheduler.py .
COPY ocr.py .
COPY worker.py .
COPY explain.py .
COPY review_generation.py .
COPY styles.py .
COPY pages.py .
COPY paper_parser.py paper_import.py ./
COPY lesson_quality.py .
COPY check_formula.cjs .
COPY --from=katex_assets / /app/katex/
ENV KATEX_ASSET_DIR=/app/katex
ENV XDG_CACHE_HOME=/tmp/studyguider-cache
COPY set_password.py .
COPY manage.html .
COPY web.html web.css web*.js ./
COPY branding/ ./branding/
RUN mkdir -p /data/uploads /tmp/studyguider-cache \
    && chown nobody:nogroup /data/uploads /tmp/studyguider-cache
USER nobody
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
