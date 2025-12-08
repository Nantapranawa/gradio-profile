FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python packages with specific versions
RUN pip install --upgrade pip && \
    pip install gradio==3.50.2 && \
    pip install huggingface-hub==0.20.0 && \
    pip install -r requirements.txt

# Copy app
COPY . .

# Expose port
EXPOSE 7860

# Health check
# HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
#     CMD python -c "import requests; requests.get('http://localhost:7860', timeout=2)"

# Run app
CMD ["python", "app_local.py"]