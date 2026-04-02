#!/usr/bin/env python3
"""Fetch all Iceberg tables and write CREATE OR REPLACE VIEW statements to a SQL file."""
import urllib.request, urllib.parse, json, os, sys

data = urllib.parse.urlencode({
    "grant_type": "client_credentials",
    "client_id": os.environ['ICEFLOW_CLIENT_ID'],
    "client_secret": os.environ['ICEFLOW_CLIENT_SECRET'],
    "scope": os.environ.get('ICEFLOW_NESSIE_SCOPE', 'iceberg-api-eu-latest'),
}).encode()

token = json.loads(urllib.request.urlopen(
    urllib.request.Request(os.environ['ICEFLOW_OAUTH2_SERVER_URI'], data=data)
).read())["access_token"]

base = f"{os.environ['ICEFLOW_NESSIE_URI'].rstrip('/')}/v1/{os.environ.get('ICEFLOW_NESSIE_PREFIX', 'main')}"
headers = {"Authorization": f"Bearer {token}"}


def get(url):
    try:
        return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=headers)).read())
    except urllib.error.HTTPError as e:
        print(f"WARNING: HTTP {e.code} for {url}", file=sys.stderr)
        return None


def ns_param(parts):
    return urllib.parse.quote("\x1f".join(parts), safe="")


def list_namespaces(parent_parts=None):
    url = f"{base}/namespaces" + (f"?parent={ns_param(parent_parts)}" if parent_parts else "")
    resp = get(url)
    return resp.get("namespaces", []) if resp else []


def list_tables(ns_parts):
    resp = get(f"{base}/namespaces/{ns_param(ns_parts)}/tables")
    return resp.get("identifiers", []) if resp else []


def walk(parent_parts=None):
    identifiers = []
    for ns_parts in list_namespaces(parent_parts):
        identifiers += list_tables(ns_parts)
        identifiers += walk(ns_parts)
    return identifiers


lines = []
for ident in walk():
    ns = ident["namespace"]   # e.g. ["default", "t2027824580", "cdc", "measurement"]
    name = ident["name"]      # e.g. "c8y_Temperature"

    # View: default.<schema>__<sub>__<table>  (skip tenant ID at ns[1])
    view_ref = f"{ns[0]}." + "__".join(ns[2:] + [name])

    # Nessie reference with each part backtick-quoted
    nessie_ref = "nessie." + ".".join(f"`{p}`" for p in ns) + f".`{name}`"

    lines.append(f"CREATE OR REPLACE VIEW {view_ref} AS SELECT * FROM {nessie_ref};")

out_path = sys.argv[1] if len(sys.argv) > 1 else "/opt/spark/create_views.sql"
with open(out_path, "w") as f:
    f.write("\n".join(lines) + "\n")

print(f"Generated {len(lines)} views -> {out_path}")
