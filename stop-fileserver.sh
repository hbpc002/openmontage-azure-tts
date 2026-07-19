#!/bin/bash
# Aggressively stop all processes on port 9090
for pid in $(lsof -ti:9090 2>/dev/null); do
  kill -9 "$pid" 2>/dev/null
done
# Also kill by process name
pkill -f "http.server 9090" 2>/dev/null
pkill -f "file_server.py" 2>/dev/null
# Wait until port is free
for i in $(seq 1 10); do
  if ! lsof -ti:9090 >/dev/null 2>&1; then
    echo "Port 9090 is free"
    exit 0
  fi
  sleep 0.5
done
echo "WARNING: Port 9090 still in use after 5 seconds"
lsof -ti:9090 2>/dev/null
exit 1
