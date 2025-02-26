# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory to /app
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code to /app
COPY . .

# Set default environment variables
ENV AWS_CONFIG_FILE=/aws-config.ini

# Run the Flask app using environment variables for configuration
ENTRYPOINT ["python", "vo-performance-bot.py", "-d", "/discord-token.txt"]