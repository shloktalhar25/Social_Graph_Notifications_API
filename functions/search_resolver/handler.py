import os
import json
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

REGION   = os.environ["AWS_ACCOUNT_REGION"]
ENDPOINT = os.environ["OPENSEARCH_ENDPOINT"]
INDEX    = os.environ["OPENSEARCH_INDEX"]

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
    timeout=15,
)


def lambda_handler(event, context):
    """
    Handles two fields:
      searchMyFollowers(searchTerm: String!)  - who follows ME
      searchMyFollowings(searchTerm: String!) - who I follow
    """
    # -- 1. Extract caller identity (never trust arguments for auth) --
    claims      = event["identity"]["claims"]
    caller_id   = claims["sub"]
    field_name  = event["info"]["fieldName"]
    search_term = event["arguments"].get("searchTerm", "").strip()
    print("SEARCH TERM:", search_term)

    if field_name == "searchMyFollowers":
        return _search_followers(caller_id, search_term)
    elif field_name == "searchMyFollowings":
        return _search_followings(caller_id, search_term)
    else:
        raise Exception(f"Unknown field: {field_name}")


def _search_followers(caller_id: str, search_term: str) -> list:
    """
    Users whose targetId = caller_id (they follow me) AND status=ACCEPTED.
    Search term matches against requesterUsername.
    """
    query = _build_query(
        fixed_field="targetId",
        fixed_value=caller_id,
        search_field="requesterUsername",
        search_term=search_term,
        
        username_field="requesterUsername",
    )
    print("CALLER ID:", caller_id)
    return _execute_search(query, return_field="requesterId", username_field="requesterUsername")


def _search_followings(caller_id: str, search_term: str) -> list:
    """
    Users whose requesterId = caller_id (I follow them) AND status=ACCEPTED.
    Search term matches against targetUsername.
    """
    query = _build_query(
        fixed_field="requesterId",
        fixed_value=caller_id,
        search_field="targetUsername",
        search_term=search_term,
        
        username_field="targetUsername",
    )
    return _execute_search(query, return_field="targetId", username_field="targetUsername")


def _build_query(
    fixed_field: str,
    fixed_value: str,
    search_field: str,
    search_term: str,
    
    username_field: str,
) -> dict:
    """
    Builds a bool query:
      - MUST match the caller's ID on the fixed_field (auth enforcement)
      - MUST have status=ACCEPTED (no pending follow leakage)
      - SHOULD match search_term on the text field (fuzzy search)
    """
    must_clauses = [
    {"term": {fixed_field: fixed_value}},
    {"term": {"status": "ACCEPTED"}},
    ]

    if search_term:
        must_clauses.append({
            "multi_match": {
                "query":     search_term,
                "fields":    [search_field, f"{search_field}.keyword"],
                "type":      "best_fields",
                "fuzziness": "AUTO",   # handles typos
            }
        })

    return {
        "query": {"bool": {"must": must_clauses}},
        "size":  50,
        "_source": [fixed_field, username_field, "requesterId", "targetId", "status", "createdAt"],
    }


def _execute_search(query: dict, return_field , username_field: str) -> list:
    response = client.search(index=INDEX, body=query)
    print("RAW RESPONSE:", response)
    hits = response["hits"]["hits"]
    

    return [
        {
            "userId":    hit["_source"].get(return_field, ""),
            "username":  hit["_source"].get(username_field, ""),
            "status":    hit["_source"].get("status", ""),
            "createdAt": hit["_source"].get("createdAt", ""),
        }
        for hit in hits
    ]