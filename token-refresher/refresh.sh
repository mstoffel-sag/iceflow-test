#!/bin/sh
set -e

# Refresh interval should be shorter than the token TTL.
# Default: 3300s (55 min) assumes a 1-hour token lifetime.
REFRESH_INTERVAL=${TOKEN_REFRESH_INTERVAL:-3300}

echo "Token refresher started (interval: ${REFRESH_INTERVAL}s)"

while true; do
  sleep "$REFRESH_INTERVAL"

  echo "Fetching new OAuth2 token..."
  TOKEN=$(curl -sf -X POST "${ICEFLOW_OAUTH2_SERVER_URI}" \
    -d "grant_type=client_credentials" \
    -d "client_id=${ICEFLOW_CLIENT_ID}" \
    -d "client_secret=${ICEFLOW_CLIENT_SECRET}" \
    -d "scope=${ICEFLOW_NESSIE_SCOPE}" \
    | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

  if [ -z "$TOKEN" ]; then
    echo "WARNING: token fetch failed, retrying next cycle" >&2
    continue
  fi

  mysql -h starrocks -P 9030 -u root -e \
    "ALTER CATALOG nessie SET (\"iceberg.catalog.token\" = \"${TOKEN}\");" \
    && echo "Catalog token updated successfully." \
    || echo "WARNING: failed to update catalog token" >&2
done
