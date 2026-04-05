# Use the official Python slim image as base
FROM python:3.11-slim

# Prevent interactive prompts during build and suppress debconf warnings
ENV DEBIAN_FRONTEND=noninteractive
ENV DEBCONF_NOWARNINGS=yes

# Set environment variables to prevent Python from writing .pyc files and buffer stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies: virtual display, screen recorder, Japanese fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    ffmpeg \
    fonts-noto-cjk \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright OS dependencies (specifically only for Firefox to save space)
RUN playwright install-deps firefox

# Run Camoufox fetch to download and properly set up the patched Firefox binaries during build
RUN python -m camoufox fetch

# Copy the entire project code into the working directory
COPY . /app

# Ensure the entrypoint script is executable
RUN chmod +x entrypoint.sh

# We map the command to an entrypoint script that launches Xvfb, sets up ffmpeg video recording manually, and starts the bot!
CMD ["./entrypoint.sh"]
