FROM python:3.11-slim

# Install Chrome and ChromeDriver
RUN apt-get update && \
    apt-get install -y wget unzip chromium chromium-driver

# Set environment variables for Selenium
ENV CHROME_BIN="/usr/bin/chromium"
ENV CHROMEDRIVER_PATH="/usr/bin/chromedriver"
ENV PATH="/usr/bin:$PATH"

# Set work directory
WORKDIR /app

# Copy code and input file
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Command to run your script
CMD ["python", "scaper.py"]
