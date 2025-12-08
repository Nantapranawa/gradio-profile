# Use a Python base image from Docker Hub
FROM python:3.8-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 5000 (change if your app uses a different port)
EXPOSE 5000

# Set the environment variable for Flask or other web frameworks (if applicable)
# ENV FLASK_APP=app_local.py  # Uncomment if you are using Flask, for example

# Run the main script or the script that starts your app
CMD python app_local.py
