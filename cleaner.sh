#!/bin/bash
# Total System Log Cleanup: Docker, PM2, and Nginx
set -e

# Ensure running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "--- Starting System-Wide Log Cleanup ---"

# 1. Truncate Docker JSON logs (Active and Rotated)
echo "Cleaning Docker container logs..."
# This handles .log, .log.1, .log.2, etc.
find /var/lib/docker/containers/ -name "*-json.log*" -exec truncate -s 0 {} +

# 2. Flush PM2 logs in all running containers
echo "Flushing PM2 in all running containers..."
for container_id in $(docker ps --format "{{.ID}}"); do
    if docker exec "$container_id" which pm2 >/dev/null 2>&1; then
        docker exec "$container_id" pm2 flush
    fi
done

# 3. Surgical Nginx Cleanup
echo "Cleaning Nginx logs..."
# Truncate active logs so Nginx doesn't need a restart
if [ -d /var/log/nginx ]; then
    find /var/log/nginx/ -name "*.log" -exec truncate -s 0 {} +

    # Delete old rotated/compressed logs (.1, .2.gz, etc.)
    # These are safe to delete because Nginx is no longer writing to them.
    find /var/log/nginx/ -type f -name "*.log.*" -delete
fi

# 4. Final Space Report
echo "--- Cleanup Complete ---"
df -h / | grep -E 'Filesystem|/$'
echo "--------------------------"
