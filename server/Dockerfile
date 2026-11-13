FROM python:3.13-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr libcairo2 nodejs \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Speech-to-text model for uploaded recordings (transcribe.py), fetched once at build time so the server never downloads at run time.
ARG WHISPER_MODEL=base
ENV WHISPER_MODEL=${WHISPER_MODEL} WHISPER_MODEL_DIR=/app/models HF_HUB_OFFLINE=1
RUN HF_HUB_OFFLINE=0 python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ['WHISPER_MODEL'], device='cpu', compute_type='int8', download_root='/app/models')"
COPY app.py .
COPY library_global.py .
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
COPY rapid.py rapid_state.py splitting.py revision.py accounts.py userspace.py mathtext.py ./
COPY check_formula.cjs .
COPY --from=katex_assets / /app/katex/
ENV KATEX_ASSET_DIR=/app/katex
ENV XDG_CACHE_HOME=/tmp/studyguider-cache
COPY game.py game_items.py transcribe.py hints.py ./
COPY fsrs_model.py clock.py curriculum.py review_plan.py ./
COPY answer_forms.py answer_media.py ./
COPY choice.py exam_import.py ./
COPY set_password.py .
COPY manage.html .
COPY web.html web.css web*.js ./
COPY branding/ ./branding/
RUN mkdir -p /data/uploads /tmp/studyguider-cache \
    && chown nobody:nogroup /data/uploads /tmp/studyguider-cache
USER nobody
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
