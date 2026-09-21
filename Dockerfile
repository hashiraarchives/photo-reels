FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium && playwright install-deps chromium

COPY *.py ./
COPY client_secret.json ./
COPY assets/ /app/assets/
COPY seed_data/ /app/seed_data/

RUN mkdir -p /tmp/aap_output/temp

ENV PYTHONUNBUFFERED=1

# Railway cron: 0 22 * * * (once daily at 10 PM UTC = 6 AM SGT)
# Runs at 6 AM SGT to give ~15h lead time before the first 9 PM publish.
# --daily now generates SHORTS_PER_DAY vertical 1-min shorts (the primary
# format since 2026-08) plus LONGFORM_PER_DAY long videos, all uploaded
# private and scheduled across the US day. `scheduler.py --shorts N` makes
# shorts only. Honors PIPELINE_PAUSED=1 (env kill switch) - see scheduler.py.
CMD ["sh", "-c", "python seed_data.py && python scheduler.py --daily"]
