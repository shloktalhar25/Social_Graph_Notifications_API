import os
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
follow_table = dynamodb.Table(os.environ["FOLLOW_TABLE_NAME"])


def lambda_handler(event, context):
    """
    Returns users I follow.
    Uses the base table (PK = USER#<myId>, SK begins_with FOLLOWS#).
    """
    caller_id = event["identity"]["claims"]["sub"]

    resp = follow_table.query(
        KeyConditionExpression=(
            Key("PK").eq(f"USER#{caller_id}") &
            Key("SK").begins_with("FOLLOWS#")
        )
    )

    return [
    {
        "userId": item["targetId"],
        "username": item.get("targetUsername", ""),      # ← was empty before
        "status": item["status"],
        "createdAt": item["createdAt"],
    }
    for item in resp.get("Items", [])
]