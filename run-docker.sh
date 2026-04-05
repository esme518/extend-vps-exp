#!/bin/bash
set -e

# Load defined environment variables from .env if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Ensure mandatory variables are set
if [ -z "$EMAIL" ] || [ -z "$PASSWORD" ]; then
    echo "Error: EMAIL and PASSWORD must be set in your environment or defined in a .env file."
    echo "Please copy .env.example to .env and fill in the values."
    exit 1
fi

IMAGE_NAME="extend-vps-bot:latest"
CONTAINER_NAME="extend-vps-runner"

echo "[1/4] Building Docker image..."
docker build -t "$IMAGE_NAME" .

echo "[2/4] Starting container..."
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

docker run --name "$CONTAINER_NAME" \
    -e EMAIL="$EMAIL" \
    -e PASSWORD="$PASSWORD" \
    -e PROXY_SERVER="$PROXY_SERVER" \
    -e DEBUG="$DEBUG" \
    "$IMAGE_NAME"

echo "[3/4] Extracting recording.webm..."
rm -f ./recording.webm 
if docker cp "$CONTAINER_NAME":/app/recording.webm ./recording.webm; then
    echo "Done: recording.webm saved to root."
else
    echo "Warning: could not find recording.webm."
fi

echo "[4/4] Cleaning up..."
docker rm -f "$CONTAINER_NAME"
echo "Process completed."
