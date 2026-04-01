#!/bin/bash
set -e

# Fetch OAuth2 token upfront so it can be written into the catalog SQL.
# StarRocks does not have built-in Iceberg OAuth2 token refresh, so the
# token is injected as a static bearer token at catalog creation time.
echo "Fetching OAuth2 token..."
TOKEN=$(curl -sf -X POST \
  "${ICEFLOW_OAUTH2_SERVER_URI}" \
  -d "grant_type=client_credentials" \
  -d "client_id=${ICEFLOW_CLIENT_ID}" \
  -d "client_secret=${ICEFLOW_CLIENT_SECRET}" \
  -d "scope=${ICEFLOW_NESSIE_SCOPE}" \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "ERROR: Failed to fetch OAuth2 token" >&2
  exit 1
fi
echo "Token fetched successfully."

# Start StarRocks (FE + BE via supervisord) in background
/bin/bash /data/deploy/entrypoint.sh &
SR_PID=$!

# Wait until FE MySQL port is open (up to 120s)
echo "Waiting for StarRocks FE on port 9030..."
for i in $(seq 1 120); do
  if mysqladmin ping -h 127.0.0.1 -P 9030 -u root --connect-timeout=2 --silent 2>/dev/null; then
    echo "StarRocks FE ready after ${i}s"
    break
  fi
  sleep 1
done

# Substitute env vars into the SQL template
sed \
  -e "s|\${ICEFLOW_OAUTH2_TOKEN}|${TOKEN}|g" \
  -e "s|\${ICEFLOW_NESSIE_URI}|${ICEFLOW_NESSIE_URI}|g" \
  -e "s|\${ICEFLOW_NESSIE_WAREHOUSE}|${ICEFLOW_NESSIE_WAREHOUSE}|g" \
  -e "s|\${ICEFLOW_NESSIE_PREFIX}|${ICEFLOW_NESSIE_PREFIX}|g" \
  -e "s|\${ICEFLOW_AWS_ACCESS_KEY}|${ICEFLOW_AWS_ACCESS_KEY}|g" \
  -e "s|\${ICEFLOW_AWS_SECRET_KEY}|${ICEFLOW_AWS_SECRET_KEY}|g" \
  -e "s|\${ICEFLOW_AWS_REGION}|${ICEFLOW_AWS_REGION}|g" \
  -e "s|\${ICEFLOW_S3_ENDPOINT}|${ICEFLOW_S3_ENDPOINT}|g" \
  /starrocks-setup/setup.sql.template > /tmp/setup.sql

# Create catalog and views
echo "Running setup SQL..."
mysql -h 127.0.0.1 -P 9030 -u root < /tmp/setup.sql \
  >/tmp/setup.log 2>&1 \
  && echo "Setup completed successfully." >> /tmp/setup.log \
  || echo "Setup failed (check /tmp/setup.log)." >> /tmp/setup.log
cat /tmp/setup.log

# Signal readiness (Docker healthcheck watches this file)
touch /tmp/starrocks_ready
echo "StarRocks is ready."

# Keep PID 1 alive
wait $SR_PID
