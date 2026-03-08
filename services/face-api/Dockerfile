FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential cmake git pkg-config \
  && rm -rf /var/lib/apt/lists/*

COPY services/face-api/pyproject.toml ./pyproject.toml
COPY services/face-api/src ./src
COPY services/face-api/entrypoint.sh /entrypoint.sh

RUN python -m pip install --upgrade pip \
  && python -m pip install . \
  && chmod +x /entrypoint.sh

EXPOSE 8020

ENTRYPOINT ["/entrypoint.sh"]
