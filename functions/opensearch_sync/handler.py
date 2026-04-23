import os
import json
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from boto3.dynamodb.types import TypeDeserializer



REGION   = os.environ["AWS_ACCOUNT_REGION"]
ENDPOINT = os.environ["OPENSEARCH_ENDPOINT"]
INDEX    = os.environ["OPENSEARCH_INDEX"]

# Build SigV4 auth once per cold start
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    refreshable_credentials=credentials,
    region=REGION,
    service="es",
)

client = OpenSearch(
    hosts=[ENDPOINT],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=30,
)

# ── Index mapping (created on first sync if not exists) ──────────
INDEX_MAPPING = {
    "settings": {
        "number_of_replicas": 1,    # 1 replica across 2 nodes = green health
        "number_of_shards":   2,
    },
    "mappings": {
        "properties": {
            "requesterId":        {"type": "keyword"},
            "requesterUsername":  {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "targetId":           {"type": "keyword"},
            "targetUsername":     {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "status":             {"type": "keyword"},
            "createdAt":          {"type": "date"},
            "entityType":         {"type": "keyword"},
        }
    },
}


def ensure_index():
    if not client.indices.exists(index=INDEX):
        print("Creating OpenSearch index...")
        client.indices.create(index=INDEX, body=INDEX_MAPPING)
    else:
        print("Index already exists")


def lambda_handler(event, context):
    ensure_index()
    failed_items = []

    for record in event["Records"]:
        message_id = record["dynamodb"]["SequenceNumber"]
        try:
            _process_record(record)
        except Exception as e:
            print(f"ERROR on record {message_id}: {e}")
            failed_items.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failed_items}


def _process_record(record: dict):
    event_name = record["eventName"]   # INSERT | MODIFY | REMOVE

    # Only process FOLLOW entity records, skip other item types
    if event_name == "REMOVE":
        old = _deserialize(record["dynamodb"].get("OldImage", {}))
        if old.get("entityType") != "FOLLOW":
            return
        doc_id = _make_doc_id(old["PK"], old["SK"])
        client.delete(index=INDEX, id=doc_id, ignore=[404])
        print(f"Deleted doc: {doc_id}")
        return

    new = _deserialize(record["dynamodb"].get("NewImage", {}))
    if new.get("entityType") != "FOLLOW":
        return



    # Extract IDs from PK/SK
    pk = new["PK"]   # USER#<id>
    sk = new["SK"]   # FOLLOW#<id>

    doc_id = _make_doc_id(pk, sk)

    requester_id = pk.replace("USER#", "")
    target_id = sk.replace("FOLLOW#", "").replace("FOLLOWS#", "")

    
    doc = {
    "requesterId":       requester_id,
    "requesterUsername": new.get("requesterUsername", ""),
    "targetId":          target_id,
    "targetUsername":    new.get("targetUsername", ""),
    "status":            new.get("status"),
    "createdAt":         new.get("createdAt"),
    "entityType":        "FOLLOW",
    }
    print("FINAL DOC:", doc)

    client.index(index=INDEX, id=doc_id, body=doc)   # ✅ FIX 2

    print(f"Indexed doc: {doc_id} status={doc['status']}")

    # index = upsert: works for both INSERT and MODIFY
    


def _make_doc_id(pk: str, sk: str) -> str:
    """Stable, unique doc ID derived from DynamoDB keys."""
    return f"{pk}#{sk}".replace("#", "_")


def _deserialize(dynamo_item: dict) -> dict:
    """Convert DynamoDB typed JSON to plain Python dict."""
    deserializer = TypeDeserializer()
    return {k: deserializer.deserialize(v) for k, v in dynamo_item.items()}

    