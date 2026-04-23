import os
import json
import boto3
import requests
from requests_aws4auth import AWS4Auth

APPSYNC_URL = os.environ["APPSYNC_API_URL"]
REGION      = os.environ.get("AWS_REGION", "us-east-1")

credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    refreshable_credentials=credentials,
    region=REGION,
    service="appsync",
)

CREATE_NOTIFICATION_MUTATION = """
mutation CreateNotification(
  $recipientId: ID!
  $senderId: ID!
  $senderUsername: String!
  $type: NotificationType!
  $message: String!
) {
  createNotification(
    recipientId: $recipientId
    senderId: $senderId
    senderUsername: $senderUsername
    type: $type
    message: $message
  ) {
    notificationId
    type
    createdAt
  }
}
"""


def lambda_handler(event, context):
    failed_items = []

    for record in event["Records"]:
        message_id = record["messageId"]
        try:
            body = json.loads(record["body"])
            _process_notification(body)
        except Exception as e:
            print(f"ERROR processing message {message_id}: {e}")
            failed_items.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failed_items}


def _process_notification(body: dict):
    event_type      = body["eventType"]
    recipient_id    = body["recipientId"]
    sender_id       = body["senderId"]
    sender_username = body["senderUsername"]
    message         = body["message"]

    response = requests.post(
        APPSYNC_URL,
        json={
            "query": CREATE_NOTIFICATION_MUTATION,
            "variables": {
                "recipientId":    recipient_id,
                "senderId":       sender_id,
                "senderUsername": sender_username,
                "type":           event_type,
                "message":        message,
            },
        },
        auth=awsauth,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )

    data = response.json()
    if "errors" in data:
        raise Exception(f"AppSync mutation failed: {data['errors']}")

    print(f"Notification created via AppSync: {event_type} for {recipient_id}")