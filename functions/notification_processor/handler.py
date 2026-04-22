import os
import boto3
import json
import uuid
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
notification_table = dynamodb.Table(os.environ["NOTIFICATION_TABLE_NAME"])


def lambda_handler(event, context):
    """
    Consumes SQS messages and writes notification records to DynamoDB.
    Uses partial batch failure reporting — failed messages return to queue.
    """
    failed_items = []

    for record in event["Records"]:
        message_id = record["messageId"]
        try:
            body = json.loads(record["body"])
            _process_notification(body)
        except Exception as e:
            print(f"ERROR processing message {message_id}: {e}")
            failed_items.append({"itemIdentifier": message_id})

    # Return failed message IDs so SQS retries only those
    return {"batchItemFailures": failed_items}


def _process_notification(body: dict):
    event_type = body["eventType"]
    recipient_id = body["recipientId"]
    sender_id = body["senderId"]
    sender_username = body["senderUsername"]
    message = body["message"]

    now = datetime.now(timezone.utc).isoformat()
    notif_id = str(uuid.uuid4())

    notification_table.put_item(
        Item={
            "PK": f"USER#{recipient_id}",
            "SK": f"NOTIF#{now}#{notif_id}",
            "notificationId": notif_id,
            "recipientId": recipient_id,
            "senderId": sender_id,
            "senderUsername": sender_username,
            "type": event_type,           # FOLLOW_REQUEST or FOLLOW_ACCEPTED
            "message": message,
            "read": False,
            "createdAt": now,
            "entityType": "NOTIFICATION",
        }
    )
    print(f"Notification written: {event_type} for user {recipient_id}")