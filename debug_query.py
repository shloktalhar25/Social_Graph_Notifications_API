# debug_query.py  (project root)
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

REGION   = "us-east-1"
ENDPOINT = "https://search-social-graph-search-qjtysjhdc3s5ce3u6cgoo6ajoy.us-east-1.es.amazonaws.com"
INDEX    = "social-follows"

# From your debug output — Bob's ID is the targetId in the follow record
BOB_ID   = "5438e458-a071-70d8-2be0-437503a12235"
ALICE_ID = "745884b8-7001-70fc-94f4-f84d962a3524"

credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    refreshable_credentials=credentials,
    region=REGION,
    service="es",
)
client = OpenSearch(
    hosts=[{"host": ENDPOINT.replace("https://", ""), "port": 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=30,
)

# ── Test 1: Exact query the Lambda uses for searchMyFollowers ────
print("=== TEST: targetId term query (what Lambda sends) ===")
resp = client.search(index=INDEX, body={
    "query": {"bool": {"must": [
        {"term": {"targetId": BOB_ID}},          # no .keyword
        {"term": {"status": "ACCEPTED"}},
    ]}},
    "size": 10,
})
print(f"Hits: {resp['hits']['total']['value']}")
for h in resp["hits"]["hits"]:
    print(h["_source"])

print()

# ── Test 2: With .keyword suffix ─────────────────────────────────
print("=== TEST: targetId.keyword term query ===")
resp = client.search(index=INDEX, body={
    "query": {"bool": {"must": [
        {"term": {"targetId.keyword": BOB_ID}},  # with .keyword
        {"term": {"status": "ACCEPTED"}},
    ]}},
    "size": 10,
})
print(f"Hits: {resp['hits']['total']['value']}")
for h in resp["hits"]["hits"]:
    print(h["_source"])

print()

# ── Test 3: Match all to confirm data ────────────────────────────
print("=== TEST: match_all ===")
resp = client.search(index=INDEX, body={"query": {"match_all": {}}, "size": 5})
print(f"Total docs: {resp['hits']['total']['value']}")
for h in resp["hits"]["hits"]:
    print(f"  targetId={h['_source']['targetId']}  status={h['_source']['status']}")