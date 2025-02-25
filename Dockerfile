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
#ENV PORT=1276

# Expose the port defined in the environment variable
#EXPOSE ${PORT}

# Run the Flask app using environment variables for configuration
ENTRYPOINT ["python", "vo-performance-bot.py"]
python -u vo-performance-bot.py -d $DISCORD_AUTH_TOKEN -c $DISCORD_CHANNEL_ID -p $PERFORMANCE_DATA_TABLE -s $SUBSCRIPTIONS_DATA_TABLE -l $ALLOWED_DM_RECIPIENTS -t $DAILY_MESSAGE_TIME