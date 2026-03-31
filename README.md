# iceflow-test

Local stack for querying [Cumulocity IceFlow](https://cumulocity.com) Iceberg data via Spark and Metabase.

## Architecture

```
Metabase (port 3000)
    └── SparkSQL connector (HiveThriftServer2, port 10000)
            └── Spark 3.5.8 + Iceberg 1.10.1
                    └── Nessie/Iceberg REST catalog (OAuth2)
                            └── S3 (cumulocity-trial-prod-iceflow-bucket)
```

Nessie tables have a 4-level deep namespace (`default > t<tenant> > cdc > <type>`) which Metabase cannot browse directly. Spark exposes them as Hive views in the `default` schema so Metabase can discover and query them.

## Prerequisites

- Docker with Docker Compose
- Credentials from your IceFlow tenant

## Setup

1. Copy the example env file and fill in your credentials:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env`:

   ```
   ICEFLOW_CLIENT_ID=<your OAuth2 client ID>
   ICEFLOW_CLIENT_SECRET=<your OAuth2 client secret>
   ICEFLOW_AWS_ACCESS_KEY=<your AWS access key>
   ICEFLOW_AWS_SECRET_KEY=<your AWS secret key>
   ```

3. Start the stack:

   ```bash
   docker compose up -d
   ```

   Spark fetches an OAuth2 token, starts HiveThriftServer2, creates the Hive views, and signals healthy. Metabase starts only after Spark is healthy and immediately syncs the views.

4. Open Metabase at http://localhost:3000

## Metabase connection settings

The SparkSQL database is configured as:

| Setting  | Value     |
| -------- | --------- |
| Engine   | SparkSQL  |
| Host     | `spark`   |
| Port     | `10000`   |
| Database | `default` |
| Username | `spark`   |

## Available views

Views are defined in `spark/create_views.sql` and created in the Hive `default` schema on startup:

| View name                           | Nessie source table                                          |
| ----------------------------------- | ------------------------------------------------------------ |
| `cdc__measurement__c8y_temperature` | `nessie.default.t2027824580.cdc.measurement.c8y_Temperature` |
| `cdc__event__event`                 | `nessie.default.t2027824580.cdc.event.event`                 |
| `cdc__event__c8y_position`          | `nessie.default.t2027824580.cdc.event.c8y_Position`          |
| `cdc__event__jobstatus`             | `nessie.default.t2027824580.cdc.event.jobStatus`             |
| `cdc__alarm__alarm`                 | `nessie.default.t2027824580.cdc.alarm.alarm`                 |
| `cdc__inventory__inventory`         | `nessie.default.t2027824580.cdc.inventory.inventory`         |
| `cdc__inventory__c8y_position`      | `nessie.default.t2027824580.cdc.inventory.c8y_Position`      |

## Adding or editing views

Edit `spark/create_views.sql` and add or modify `CREATE OR REPLACE VIEW` statements:

```sql
CREATE OR REPLACE VIEW default.my_view AS
SELECT * FROM nessie.`default`.`t2027824580`.`cdc`.`<type>`.`<table>`;
```

Then restart Spark to recreate all views:

```bash
docker compose restart spark
```

To verify views after restart:

```bash
docker exec spark /opt/spark/bin/beeline -u "jdbc:hive2://localhost:10000" -n spark \
  -e "SHOW TABLES IN default;"
```

Trigger a Metabase schema resync after adding views: Admin → Databases → Spark → Sync database schema now.

## Querying data

Use Metabase's visual query builder or SQL editor. Example:

```sql
SELECT T.value, T.unit, time, source
FROM default.cdc__measurement__c8y_temperature
ORDER BY time DESC
LIMIT 100
```

Note: `T` is a struct column — access fields with `T.value` and `T.unit`.

> **Note:** The inventory table is a CDC log, not a deduplicated dimension table. Each device update creates a new row. Use a `ROW_NUMBER()` window function to get the latest state per device if joining to measurements.

## Spark UI

Available at http://localhost:4040 while Spark is running.

## File structure

```
.
├── docker-compose.yml              # Spark + Metabase services
├── .env                            # Credentials (gitignored)
├── .env.example                    # Credentials template
├── spark-conf/
│   └── spark-defaults.conf         # Iceberg/Nessie catalog config template
└── spark/
    ├── Dockerfile                  # Spark 3.5.8 image with Iceberg + S3 JARs
    ├── entrypoint.sh               # Fetches OAuth2 token, starts Thrift Server, creates views
    └── create_views.sql            # Hive view definitions (edit to add/change views)
```

## Troubleshooting

**Spark exits with OOM / SIGSEGV**
Increase `mem_limit` for the spark service in `docker-compose.yml` (currently `4g`).

**Metabase exits with code 137 (OOM)**
Increase `mem_limit` for the metabase service (currently `4g`) and `-Xmx` in `JAVA_TOOL_OPTIONS`.

**Views not appearing in Metabase**
Check view creation log inside the container:

```bash
docker exec spark cat /tmp/create_views.log
```

Then trigger a manual resync in Metabase: Admin → Databases → Spark → Sync database schema now.

**OAuth2 token fetch fails on startup**
Spark will exit immediately. Check `docker logs spark` for the error. Verify `ICEFLOW_CLIENT_ID` and `ICEFLOW_CLIENT_SECRET` in `.env`.
