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

# Copy the new shell script into the container
COPY start.sh /app/start.sh

# Make the shell script executable
RUN chmod +x /app/start.sh

# Expose port 5000 (adjust if your app uses a different port)
EXPOSE 5000

# Run the start.sh shell script
CMD ["./start.sh"]
