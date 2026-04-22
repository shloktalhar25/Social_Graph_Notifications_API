import os
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
follow_table = dynamodb.Table(os.environ["FOLLOW_TABLE_NAME"])


def lambda_handler(event, context):
    """
    Returns users who follow ME.
    Uses the GSI (GSI_PK = USER#<myId>) to query reverse direction.
    """
    caller_id = event["identity"]["claims"]["sub"]

    resp = follow_table.query(
        IndexName="GSI-FollowerIndex",
        KeyConditionExpression=Key("GSI_PK").eq(f"USER#{caller_id}"),
    )

    return [
    {
        "userId": item["requesterId"],
        "username": item.get("requesterUsername", ""),   # ← was empty before
        "status": item["status"],
        "createdAt": item["createdAt"],
    }
    for item in resp.get("Items", [])
]