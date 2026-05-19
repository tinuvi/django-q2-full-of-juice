FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev gettext \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip \
    && pip install poetry==1.8.2 \
    && poetry config virtualenvs.create false --local

COPY poetry.lock pyproject.toml LICENSE ./

RUN poetry install --no-root --with dev --all-extras

COPY . ./

RUN pip install --no-deps -e .
