import os
import boto3
import uuid
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
notification_table = dynamodb.Table(os.environ["NOTIFICATION_TABLE_NAME"])


def lambda_handler(event, context):
    """
    Called by notification processor via IAM-signed AppSync mutation.
    Writes notification to DynamoDB AND triggers onNewNotification subscription.
    The subscription fires because AppSync sees this as a mutation result.
    """
    args = event["arguments"]
    now  = datetime.now(timezone.utc).isoformat()
    notif_id = str(uuid.uuid4())

    notification_table.put_item(
        Item={
            "PK":             f"USER#{args['recipientId']}",
            "SK":             f"NOTIF#{now}#{notif_id}",
            "notificationId": notif_id,
            "recipientId":    args["recipientId"],
            "senderId":       args["senderId"],
            "senderUsername": args["senderUsername"],
            "type":           args["type"],
            "message":        args["message"],
            "read":           False,
            "createdAt":      now,
            "entityType":     "NOTIFICATION",
        }
    )

    return {
        "notificationId": notif_id,
        "recipientId":    args["recipientId"],
        "senderId":       args["senderId"],
        "senderUsername": args["senderUsername"],
        "type":           args["type"],
        "message":        args["message"],
        "createdAt":      now,
        "read":           False,
    }