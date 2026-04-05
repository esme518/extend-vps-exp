#!/bin/bash

# Configure the virtual display natively
export DISPLAY=:99
Xvfb :99 -screen 0 1280x720x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Wait for Xvfb to be fully ready
sleep 2

# Start ffmpeg to silently record the entire virtual screen into recording.webm
echo "Starting desktop recorder (ffmpeg)..."
ffmpeg -y -f x11grab -video_size 1280x720 -i :99 -codec:v libvpx -b:v 1M -r 15 recording.webm > /dev/null 2>&1 &
FFMPEG_PID=$!

# Run the python script 
echo "Starting bot script..."
python main.py
BOT_EXIT_CODE=$?

echo "Bot finished. Stopping recorder..."
# Send polite interrupt to ffmpeg so it properly flushes the corrupted webm tail
kill -2 $FFMPEG_PID
wait $FFMPEG_PID || true

echo "Recording saved. Shutting down system."
kill $XVFB_PID || true

exit $BOT_EXIT_CODE
