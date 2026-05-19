# Build context MUST be the repo root so we can install django-q2 from source.
# See sample-project/docker-compose.yml for the wiring.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /lib

RUN pip install --upgrade pip && \
    pip install poetry==2.4.1 && \
    poetry config virtualenvs.create false --local

# --- Install django-q2 (and the dev deps the sample needs) from the workspace source ---
COPY pyproject.toml poetry.lock LICENSE README.rst ./
COPY django_q ./django_q

RUN poetry install --no-root --only main && pip install --no-deps -e .

# --- Add the sample project on top ---
WORKDIR /app
COPY sample-project ./

RUN chmod +x ./scripts/*.sh
