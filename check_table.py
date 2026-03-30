import urllib.request, urllib.parse, json, os, sys

client_id = os.environ['ICEFLOW_CLIENT_ID']
client_secret = os.environ['ICEFLOW_CLIENT_SECRET']

# Get OAuth2 token
data = urllib.parse.urlencode({
    "grant_type": "client_credentials",
    "client_id": client_id,
    "client_secret": client_secret,
    "scope": "iceberg-api-eu-latest",
}).encode()

req = urllib.request.Request(
    "https://keycloak.monitor.c8y.io/realms/IceFlow/protocol/openid-connect/token",
    data=data
)
token = json.loads(urllib.request.urlopen(req).read())["access_token"]

base = "https://iceberg.eu-latest.cumulocity.com:19120/iceberg/v1"
headers = {"Authorization": f"Bearer {token}"}

# The config response says prefix="main", so all table/namespace calls go under /main/
prefixed_base = f"{base}/main"

def check_table(namespace, table):
    # Iceberg REST API encodes multi-level namespaces with \x1F (unit separator)
    ns_encoded = urllib.parse.quote("\x1f".join(namespace.split(".")), safe="")
    url = f"{prefixed_base}/namespaces/{ns_encoded}/tables/{table}"
    req2 = urllib.request.Request(url, headers=headers)
    print(f"\n=== {namespace} / {table} ===")
    print(f"  URL: {url}")
    try:
        resp = json.loads(urllib.request.urlopen(req2).read())
        meta_loc = resp.get("metadata-location") or resp.get("metadataLocation", "not found")
        table_loc = resp.get("metadata", {}).get("location", "no location")
        snapshots = resp.get("metadata", {}).get("snapshots", [])
        current_snapshot_id = resp.get("metadata", {}).get("current-snapshot-id", "none")
        print(f"  metadata-location:  {meta_loc}")
        print(f"  table location:     {table_loc}")
        print(f"  current-snapshot:   {current_snapshot_id}")
        print(f"  snapshot count:     {len(snapshots)}")
        if snapshots:
            last = snapshots[-1]
            print(f"  last manifest-list: {last.get('manifest-list', 'n/a')}")
        return resp
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  HTTP {e.code}: {body[:300]}")
        return None

# List ALL tables in ALL namespaces to find exact casing
interesting_ns = [
    "default.t2027824580.cdc.measurement",
    "default.t2027824580.cdc.inventory",
    "default.t2027824580.cdc.event",
]
for ns in interesting_ns:
    ns_encoded = urllib.parse.quote("\x1f".join(ns.split(".")), safe="")
    url = f"{prefixed_base}/namespaces/{ns_encoded}/tables"
    req3 = urllib.request.Request(url, headers=headers)
    print(f"\n=== Tables in {ns} ===")
    try:
        resp = json.loads(urllib.request.urlopen(req3).read())
        for ident in resp.get("identifiers", []):
            name = ident.get("name")
            # Try to load its metadata
            turl = f"{prefixed_base}/namespaces/{ns_encoded}/tables/{name}"
            try:
                tr = json.loads(urllib.request.urlopen(urllib.request.Request(turl, headers=headers)).read())
                meta = tr.get("metadata-location", "no metadata-location")
                snaps = len(tr.get("metadata", {}).get("snapshots", []))
                print(f"  {name}  metadata={meta.split('/')[-1]}  snapshots={snaps}")
            except urllib.error.HTTPError as te:
                print(f"  {name}  -> HTTP {te.code}")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
