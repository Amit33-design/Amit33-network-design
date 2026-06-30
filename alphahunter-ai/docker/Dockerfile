FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

# backend.main:app is the FastAPI ASGI app.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
