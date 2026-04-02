#!/bin/bash
set -e

SPARK_HOME=${SPARK_HOME:-/opt/spark}

# Fetch OAuth2 token upfront and inject it as a static bearer token.
# This avoids Iceberg's built-in OAuth2 flow which fails when Nessie
# requires auth even on the /v1/config discovery endpoint.
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

# Write spark-defaults.conf with all placeholders substituted
mkdir -p "$SPARK_HOME/conf"
sed \
  -e "s|\${ICEFLOW_OAUTH2_TOKEN}|${TOKEN}|g" \
  -e "s|\${ICEFLOW_CLIENT_ID}|${ICEFLOW_CLIENT_ID}|g" \
  -e "s|\${ICEFLOW_CLIENT_SECRET}|${ICEFLOW_CLIENT_SECRET}|g" \
  -e "s|\${ICEFLOW_NESSIE_URI}|${ICEFLOW_NESSIE_URI}|g" \
  -e "s|\${ICEFLOW_NESSIE_WAREHOUSE}|${ICEFLOW_NESSIE_WAREHOUSE}|g" \
  -e "s|\${ICEFLOW_NESSIE_PREFIX}|${ICEFLOW_NESSIE_PREFIX}|g" \
  -e "s|\${ICEFLOW_NESSIE_SCOPE}|${ICEFLOW_NESSIE_SCOPE}|g" \
  -e "s|\${ICEFLOW_OAUTH2_SERVER_URI}|${ICEFLOW_OAUTH2_SERVER_URI}|g" \
  -e "s|\${ICEFLOW_S3_ENDPOINT}|${ICEFLOW_S3_ENDPOINT}|g" \
  /spark-conf/spark-defaults.conf > "$SPARK_HOME/conf/spark-defaults.conf"

rm -f /tmp/spark_ready

# Start Thrift Server in background so we can create views before signaling healthy
"$SPARK_HOME/bin/spark-submit" \
  --master local[*] \
  --driver-memory 2560m \
  --class org.apache.spark.sql.hive.thriftserver.HiveThriftServer2 \
  --conf spark.hive.server2.thrift.port=10000 \
  --conf spark.hive.server2.thrift.bind.host=0.0.0.0 &
SPARK_PID=$!

# Wait until Thrift Server port is open (up to 120s)
echo "Waiting for Thrift Server on port 10000..."
for i in $(seq 1 120); do
  if bash -c '</dev/tcp/localhost/10000' 2>/dev/null; then
    echo "Thrift Server ready after ${i}s"
    break
  fi
  sleep 1
done

# Regenerate views from live Iceberg catalog
echo "Generating Hive views from Iceberg catalog..."
python3 /opt/spark/generate_views.py /tmp/create_views.sql

# Create (or recreate) Hive views so Metabase can browse the Nessie tables
echo "Creating Hive views..."
"$SPARK_HOME/bin/beeline" -u "jdbc:hive2://localhost:10000" -n spark \
  -f /tmp/create_views.sql \
  >/tmp/create_views.log 2>&1 \
  && echo "Views created successfully" >> /tmp/create_views.log \
  || echo "View creation failed" >> /tmp/create_views.log
cat /tmp/create_views.log

# Signal that Spark + views are ready (Docker healthcheck watches this file)
touch /tmp/spark_ready
echo "Spark is ready."

# Periodically refresh views to pick up new Iceberg tables (every 5 minutes)
(while true; do
  sleep 300
  echo "Refreshing Hive views from Iceberg catalog..."
  python3 /opt/spark/generate_views.py /tmp/create_views.sql \
    && "$SPARK_HOME/bin/beeline" -u "jdbc:hive2://localhost:10000" -n spark \
         -f /tmp/create_views.sql >/tmp/create_views.log 2>&1 \
    && echo "Views refreshed successfully." \
    || echo "View refresh failed, will retry next cycle."
done) &

# Keep PID 1 alive by waiting for Spark
wait $SPARK_PID
