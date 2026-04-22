import os
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
notification_table = dynamodb.Table(os.environ["NOTIFICATION_TABLE_NAME"])


def lambda_handler(event, context):
    """
    Returns notifications for the calling user.
    Sorted newest-first via ScanIndexForward=False.
    """
    caller_id = event["identity"]["claims"]["sub"]

    resp = notification_table.query(
        KeyConditionExpression=(
            Key("PK").eq(f"USER#{caller_id}") &
            Key("SK").begins_with("NOTIF#")
        ),
        ScanIndexForward=False,   # newest first
        Limit=50,                 # page size — keep it bounded
    )

    return [
        {
            "notificationId": item["notificationId"],
            "recipientId":    item["recipientId"],
            "senderId":       item["senderId"],
            "senderUsername": item["senderUsername"],
            "type":           item["type"],
            "message":        item["message"],
            "createdAt":      item["createdAt"],
            "read":           item.get("read", False),
        }
        for item in resp.get("Items", [])
    ]