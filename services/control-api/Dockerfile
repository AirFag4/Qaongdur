FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY services/control-api/pyproject.toml ./pyproject.toml
COPY services/control-api/src ./src

RUN python -m pip install --upgrade pip && python -m pip install .

EXPOSE 8000

CMD ["uvicorn", "control_api.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
