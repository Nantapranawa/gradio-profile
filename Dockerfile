# Use a Python base image from Docker Hub
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Upgrade pip to ensure it's the latest version
RUN pip install --upgrade pip

# Install dependencies from requirements.txt
# Adding the '--no-cache-dir' to reduce image size by avoiding pip cache
RUN pip install --no-cache-dir -r requirements.txt

# Add extra steps to ensure compatibility between gradio and huggingface-hub
# Install specific compatible versions of gradio and huggingface-hub if necessary
RUN pip install gradio==4.44.1 huggingface-hub==1.2.1

# Expose port 5000 (adjust if your app uses a different port)
EXPOSE 5000

# Run the main script that starts your app
CMD ["python", "app_local.py"]
