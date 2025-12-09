# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Create equivalent shell script from .bat commands
# Option 1: Direct translation of .bat to shell
# Create a shell script that does what your .bat does
RUN echo '#!/bin/bash\npython main.py' > start.sh && \
    chmod +x start.sh

# OR Option 2: If .bat sets environment variables and runs commands
# You can set them in Dockerfile directly

# Expose port (adjust based on your app)
EXPOSE 8000

# Run the application
# Method A: Direct Python command
CMD ["python", "app_local.py"]

# Method B: Use the shell script
# CMD ["./start.sh"]

# Method C: For web apps (like Flask/FastAPI)
# CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8000"]