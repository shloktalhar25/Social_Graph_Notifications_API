# debug_opensearch.py  (put in project root)
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

REGION   = "us-east-1"
ENDPOINT = "search-social-graph-search-qjtysjhdc3s5ce3u6cgoo6ajoy.us-east-1.es.amazonaws.com"  # from cdk deploy output

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
)

# 1. Check all docs in index
print("=== ALL DOCS IN INDEX ===")
resp = client.search(index="social-follows", body={"query": {"match_all": {}}, "size": 20})
for hit in resp["hits"]["hits"]:
    print(hit["_id"])
    print(hit["_source"])
    print("---")

# 2. Check index mapping
print("\n=== INDEX MAPPING ===")
mapping = client.indices.get_mapping(index="social-follows")
print(mapping)