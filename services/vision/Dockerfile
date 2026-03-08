FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends ffmpeg libglib2.0-0 libsm6 libxext6 \
  && rm -rf /var/lib/apt/lists/*

COPY services/vision/pyproject.toml ./pyproject.toml
COPY services/vision/src ./src

RUN python -m pip install --upgrade pip \
  && python -m pip install . \
  && python -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision \
  && python -m pip install 'ultralytics>=8.3.0' 'open-clip-torch>=2.30.0' \
  && python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

EXPOSE 8010

CMD ["uvicorn", "vision_service.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8010"]
