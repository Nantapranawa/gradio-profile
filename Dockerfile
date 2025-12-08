# Use a Python base image from Docker Hub
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Upgrade pip to ensure it's the latest version
RUN pip install --upgrade pip

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 5000 (adjust if your app uses a different port)
EXPOSE 5000

# If you need to run a shell script (start.sh) in Railway, make sure it's correctly referenced:
RUN chmod +x start.sh

# Use CMD to run the Python script directly or use the start.sh script.
# If `start.sh` is essential to your app startup, ensure it's copied properly to the container.
CMD ["sh", "start.sh"]
