# ==============================================================================
# Khmer Government Document Intelligence System - Production Dockerfile
# ==============================================================================

FROM python:3.12-slim-bookworm

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /app

# Install system dependencies:
# - tesseract-ocr, tesseract-ocr-eng, tesseract-ocr-khm (Official Debian Khmer & English OCR models)
# - fonts-khmeros (Official Khmer OS Unicode fonts for Khmer document rendering)
# - libgl1, libglib2.0-0 (OpenCV dependencies)
# - curl (Container health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-khm \
    fonts-khmeros \
    fonts-noto-core \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set default Tesseract binary and tessdata paths for Debian/Ubuntu Linux
ENV TESSERACT_CMD=/usr/bin/tesseract \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata \
    OCR_DEFAULT_LANGUAGES=khm+eng

# Install Python requirements
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app /app/app
COPY test_ocr.py /app/test_ocr.py

# Create directory for secure document storage
RUN mkdir -p /app/uploads/documents

# Expose FastAPI HTTP port
EXPOSE 8000

# Healthcheck to ensure FastAPI and OCR engine are responsive
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run with production Uvicorn ASGI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
