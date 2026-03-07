FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY services/vision/pyproject.toml ./pyproject.toml
COPY services/vision/src ./src

RUN python -m pip install --upgrade pip && python -m pip install .

EXPOSE 8010

CMD ["uvicorn", "vision_service.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8010"]
