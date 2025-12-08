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

# If start.bat is needed, make sure it is executable in the container
# Create a script to run the bat file inside the container
RUN chmod +x start.bat

# Expose port 5000 (adjust if your app uses a different port)
EXPOSE 5000

# Run the start.bat file in the container
CMD ["sh", "-c", "start.bat"]
