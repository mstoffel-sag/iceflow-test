# iceflow-test

Local stack for querying [Cumulocity IceFlow](https://cumulocity.com) Iceberg data via Trino and Metabase.

## Architecture

```
Metabase (port 3000)
    └── Starburst/Trino connector (HTTP, no SSL)
            └── Trino (port 8080)
                    └── Nessie/Iceberg REST catalog
                            └── S3 (cumulocity-trial-prod-iceflow-bucket)
```

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

4. Open Metabase at http://localhost:3000

## Metabase connection settings

The Trino database should be configured in Metabase with:

| Setting   | Value             |
| --------- | ----------------- |
| Connector | Starburst (Trino) |
| Host      | `trino`           |
| Port      | `8080`            |
| Catalog   | `nessie`          |
| SSL       | off               |
| Username  | `trino`           |

> **Tip:** In Admin → Databases → Trino → Scheduling, set "Scan for filter values" to **Never** to avoid an endless sync spinner.

## Querying data

Metabase's visual table browser does not support Trino's nested namespace schema naming (schemas like `default.t<tenant>.cdc.inventory`). Use **New → SQL query** instead.

### Available tables

| Table       | Schema                              | Rows (approx.) |
| ----------- | ----------------------------------- | -------------- |
| `inventory` | `default.t2027824580.cdc.inventory` | ~312k          |
| `event`     | `default.t2027824580.cdc.event`     | ~315k          |
| `alarm`     | `default.t2027824580.cdc.alarm`     | ~500           |
| `operation` | `default.t2027824580.cdc.operation` | 0              |

### Query syntax

Schemas with dots in the name must be double-quoted:

```sql
SELECT *
FROM nessie."default.t2027824580.cdc.inventory".inventory
LIMIT 100
```

```sql
SELECT *
FROM nessie."default.t2027824580.cdc.event".event
LIMIT 100
```

```sql
SELECT *
FROM nessie."default.t2027824580.cdc.alarm".alarm
LIMIT 100
```

## File structure

```
.
├── docker-compose.yml          # Trino + Metabase services
├── .env                        # Credentials (gitignored)
├── .env.example                # Credentials template
└── etc/
    ├── config.properties       # Trino node config
    ├── jvm.config              # Trino JVM settings
    ├── log.properties          # Trino log levels
    ├── node.properties         # Trino node identity
    └── catalog/
        └── nessie.properties   # Iceberg REST catalog config (reads from .env)
```

## Troubleshooting

**Trino exits with code 137 (OOM)**
Increase `mem_limit` and `-Xmx` in `docker-compose.yml`. Current limits: Trino `2g` / `1500m`.

**Metabase exits with code 137 (OOM)**
Increase `mem_limit` and `-Xmx` for the metabase service. Current limits: `4g` / `3g`.

**`TABLE_NOT_FOUND` on SELECT**
Only certain tables are queryable — see the table above. Some tables visible in `SHOW TABLES` have broken metadata on the remote Iceberg catalog and cannot be queried.

**Metabase sync spinner never stops**
Go to Admin → Databases → Trino → Scheduling and set "Scan for filter values" to Never.
