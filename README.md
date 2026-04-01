# iceflow-test

Local stack for querying [Cumulocity IceFlow](https://cumulocity.com) Iceberg data via StarRocks and Metabase.

## Architecture

```
Metabase (port 3000)
    └── StarRocks driver (port 9030)
            └── StarRocks (FE + BE, allin1)
                    └── External Nessie/Iceberg REST catalog (OAuth2)
                            └── S3 (cumulocity-trial-prod-iceflow-bucket)
```

StarRocks mounts an external Iceberg catalog (`nessie`) backed by the Nessie REST API. Nessie tables have a 4-level deep namespace (`default > t<tenant> > cdc > <type>`) which Metabase cannot browse directly. StarRocks exposes them as views in a local `iceflow` database so Metabase can discover and query them via the bundled StarRocks driver.

Because StarRocks does not support automatic OAuth2 token refresh, a lightweight `token-refresher` sidecar re-fetches the token periodically and updates the catalog via `ALTER CATALOG`.

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
   # OAuth2 credentials
   ICEFLOW_CLIENT_ID=<your OAuth2 client ID>
   ICEFLOW_CLIENT_SECRET=<your OAuth2 client secret>

   # Nessie / Iceberg catalog
   ICEFLOW_NESSIE_URI=<Nessie REST endpoint>
   ICEFLOW_NESSIE_WAREHOUSE=<warehouse location>
   ICEFLOW_NESSIE_PREFIX=main
   ICEFLOW_NESSIE_SCOPE=<OAuth2 scope>
   ICEFLOW_OAUTH2_SERVER_URI=<token endpoint>

   # S3 / AWS
   ICEFLOW_AWS_ACCESS_KEY=<your AWS access key>
   ICEFLOW_AWS_SECRET_KEY=<your AWS secret key>
   ICEFLOW_AWS_REGION=<region>
   ICEFLOW_S3_ENDPOINT=<S3-compatible endpoint>
   ```

3. Start the stack:

   ```bash
   docker compose up -d
   ```

   StarRocks fetches an OAuth2 token on startup, creates the external catalog and `iceflow` views, then signals healthy. Metabase and the token-refresher sidecar start only after StarRocks is healthy.

4. Open Metabase at http://localhost:3000

## Metabase connection settings

Metabase uses a custom StarRocks driver (bundled in the `metabase/` image). Add a new database with:

| Setting  | Value              |
| -------- | ------------------ |
| Engine   | StarRocks          |
| Host     | `starrocks`        |
| Port     | `9030`             |
| Catalog  | `default_catalog`  |
| Database | `iceflow`          |
| Username | `root`             |

## Available views

Views are defined in `starrocks/setup.sql.template` and created in the `iceflow` database on startup:

| View name                              | Nessie source table                                                  |
| -------------------------------------- | -------------------------------------------------------------------- |
| `cdc__measurement__c8y_Temperature`    | `nessie.default.t2027824580.cdc.measurement.c8y_Temperature`        |
| `cdc__event__event`                    | `nessie.default.t2027824580.cdc.event.event`                        |
| `cdc__event__c8y_Position`             | `nessie.default.t2027824580.cdc.event.c8y_Position`                 |
| `cdc__event__jobStatus`                | `nessie.default.t2027824580.cdc.event.jobStatus`                    |
| `cdc__alarm__alarm`                    | `nessie.default.t2027824580.cdc.alarm.alarm`                        |
| `cdc__inventory__inventory`            | `nessie.default.t2027824580.cdc.inventory.inventory`                |
| `cdc__inventory__c8y_Position`         | `nessie.default.t2027824580.cdc.inventory.c8y_Position`             |

## Adding or editing views

Edit `starrocks/setup.sql.template` and add or modify `CREATE VIEW` statements:

```sql
CREATE VIEW IF NOT EXISTS iceflow.my_view AS
  SELECT * FROM nessie.`default.t2027824580.cdc.<type>`.<table>;
```

Then rebuild and restart StarRocks to recreate all views:

```bash
docker compose build starrocks && docker compose restart starrocks
```

To verify views after restart:

```bash
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -u root -e "SHOW TABLES IN iceflow;"
```

Trigger a Metabase schema resync after adding views: Admin → Databases → iceflow → Sync database schema now.

## Token refresh

The `token-refresher` sidecar runs on a configurable interval (default: 3300s / 55 min) and keeps the catalog token fresh by issuing `ALTER CATALOG nessie SET (...)` against StarRocks. Set `TOKEN_REFRESH_INTERVAL` in `.env` to match your token TTL.

## Querying data

Use Metabase's visual query builder or SQL editor. Example:

```sql
SELECT *
FROM iceflow.cdc__measurement__c8y_Temperature
ORDER BY time DESC
LIMIT 100;
```

> **Note:** The inventory table is a CDC log, not a deduplicated dimension table. Each device update creates a new row. Use a `ROW_NUMBER()` window function to get the latest state per device if joining to measurements.

## File structure

```
.
├── docker-compose.yml                   # StarRocks + Metabase + token-refresher services
├── .env                                 # Credentials (gitignored)
├── .env.example                         # Credentials template
├── check_table.py                       # Inspect Iceberg tables via the REST API directly
├── starrocks/
│   ├── Dockerfile                       # starrocks/allin1-ubuntu with curl + mysql-client
│   ├── entrypoint.sh                    # Fetches OAuth2 token, starts StarRocks, runs setup SQL
│   └── setup.sql.template               # External catalog + iceflow views DDL
├── metabase/
│   ├── Dockerfile                       # Official Metabase image with StarRocks driver bundled
│   └── starrocks.metabase-driver-*.jar  # StarRocks Metabase driver JAR
└── token-refresher/
    └── refresh.sh                       # Periodic OAuth2 token refresh via ALTER CATALOG
```

## Inspecting the catalog directly

`check_table.py` queries the Iceberg REST API directly (bypassing StarRocks) to inspect table metadata. Useful for verifying table names, snapshot counts, and metadata locations before configuring views.

```bash
ICEFLOW_CLIENT_ID=... ICEFLOW_CLIENT_SECRET=... python check_table.py
```

It lists all tables under the `measurement`, `inventory`, and `event` namespaces and prints metadata location, current snapshot, and manifest list for each.

## Troubleshooting

**StarRocks exits with OOM**
Increase `mem_limit` for the starrocks service in `docker-compose.yml` (currently `6g`).

**Metabase exits with code 137 (OOM)**
Increase `mem_limit` for the metabase service (currently `4g`) and `-Xmx` in `JAVA_TOOL_OPTIONS`.

**Views not appearing in Metabase**
Check setup SQL output in the container logs:

```bash
docker logs starrocks
```

Or inspect the setup log directly:

```bash
docker exec starrocks cat /tmp/setup.log
```

Then trigger a manual resync in Metabase: Admin → Databases → iceflow → Sync database schema now.

**OAuth2 token fetch fails on startup**
StarRocks will exit immediately. Check `docker logs starrocks` and verify `ICEFLOW_CLIENT_ID` and `ICEFLOW_CLIENT_SECRET` in `.env`.

**Catalog token expired mid-session**
The token-refresher handles this automatically. If it falls behind, check `docker logs token-refresher`.
