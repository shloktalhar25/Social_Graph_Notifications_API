import os
import boto3
import json
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

follow_table = dynamodb.Table(os.environ["FOLLOW_TABLE_NAME"])
user_table = dynamodb.Table(os.environ["USER_TABLE_NAME"])
queue_url = os.environ["NOTIFICATION_QUEUE_URL"]


def lambda_handler(event, context):
    # -- 1. Extract caller identity ----------------------------
    claims = event["identity"]["claims"]
    acceptor_id = claims["sub"]           # the person accepting
    acceptor_username = claims["cognito:username"]

    requester_id = event["arguments"]["requesterId"]

    # -- 2. Authorization: only the recipient can accept -------
    # Fetch the follow record
    follow_resp = follow_table.get_item(
        Key={
            "PK": f"USER#{requester_id}",
            "SK": f"FOLLOWS#{acceptor_id}",
        }
    )

    if "Item" not in follow_resp:
        raise Exception("FOLLOW_REQUEST_NOT_FOUND")

    follow_item = follow_resp["Item"]

    # The targetId in the record MUST match the caller
    if follow_item["targetId"] != acceptor_id:
        raise Exception("UNAUTHORIZED: you can only accept requests sent to you")

    if follow_item["status"] != "PENDING":
        raise Exception("FOLLOW_REQUEST_ALREADY_PROCESSED")

    now = datetime.now(timezone.utc).isoformat()

    # -- 3. Update status to ACCEPTED -------------------------
    follow_table.update_item(
        Key={
            "PK": f"USER#{requester_id}",
            "SK": f"FOLLOWS#{acceptor_id}",
        },
        UpdateExpression="SET #s = :accepted, updatedAt = :now",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":accepted": "ACCEPTED",
            ":pending": "PENDING",
            ":now": now,
        },
        # Optimistic lock: only update if still PENDING
        ConditionExpression="#s = :pending",
    )

    # -- 4. Fetch requester info for the response --------------
    requester_resp = user_table.get_item(
        Key={"PK": f"USER#{requester_id}", "SK": "PROFILE"}
    )
    requester = requester_resp.get("Item", {})

    # -- 5. Publish FOLLOW_ACCEPTED event to SQS ---------------
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({
            "eventType": "FOLLOW_ACCEPTED",
            "recipientId": requester_id,        # notify the requester
            "senderId": acceptor_id,
            "senderUsername": acceptor_username,
            "message": f"{acceptor_username} accepted your follow request",
        }),
    )

    return {
        "userId": requester_id,
        "username": requester.get("username", ""),
        "status": "ACCEPTED",
        "createdAt": follow_item["createdAt"],
    }