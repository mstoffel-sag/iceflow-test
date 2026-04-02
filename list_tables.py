import urllib.request, urllib.parse, json, os

client_id = os.environ['ICEFLOW_CLIENT_ID']
client_secret = os.environ['ICEFLOW_CLIENT_SECRET']

# Get OAuth2 token
data = urllib.parse.urlencode({
    "grant_type": "client_credentials",
    "client_id": client_id,
    "client_secret": client_secret,
    "scope": os.environ.get('ICEFLOW_NESSIE_SCOPE', 'iceberg-api-eu-latest'),
}).encode()

token_url = os.environ.get('ICEFLOW_OAUTH2_SERVER_URI',
    'https://keycloak.monitor.c8y.io/realms/IceFlow/protocol/openid-connect/token')
token = json.loads(urllib.request.urlopen(
    urllib.request.Request(token_url, data=data)
).read())["access_token"]

nessie_uri = os.environ.get('ICEFLOW_NESSIE_URI', 'https://iceberg.eu-latest.cumulocity.com:19120/iceberg/')
prefix = os.environ.get('ICEFLOW_NESSIE_PREFIX', 'main')
base = f"{nessie_uri.rstrip('/')}/v1/{prefix}"
headers = {"Authorization": f"Bearer {token}"}


def get(url):
    req = urllib.request.Request(url, headers=headers)
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {url}: {e.read().decode()[:200]}")
        return None


def ns_param(parts):
    """Encode namespace parts as \x1F-separated string, URL-encoded."""
    return urllib.parse.quote("\x1f".join(parts), safe="")


def list_namespaces(parent_parts=None):
    """Return list of namespace part-lists directly under parent."""
    url = f"{base}/namespaces"
    if parent_parts:
        url += f"?parent={ns_param(parent_parts)}"
    resp = get(url)
    if not resp:
        return []
    return resp.get("namespaces", [])


def list_tables(ns_parts):
    """Return list of fully-qualified table names in the given namespace."""
    url = f"{base}/namespaces/{ns_param(ns_parts)}/tables"
    resp = get(url)
    if not resp:
        return []
    return [
        ".".join(ident["namespace"]) + "." + ident["name"]
        for ident in resp.get("identifiers", [])
    ]


def walk(parent_parts=None):
    """Recursively walk namespaces and collect all table identifiers."""
    tables = []
    for ns_parts in list_namespaces(parent_parts):
        tables += list_tables(ns_parts)
        tables += walk(ns_parts)
    return tables


all_tables = walk()

print(f"\nFound {len(all_tables)} tables:")
for t in sorted(all_tables):
    print(f"  {t}")
