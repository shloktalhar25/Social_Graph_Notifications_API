import os
import boto3
import json
import uuid
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

follow_table = dynamodb.Table(os.environ["FOLLOW_TABLE_NAME"])
user_table = dynamodb.Table(os.environ["USER_TABLE_NAME"])
queue_url = os.environ["NOTIFICATION_QUEUE_URL"]


def lambda_handler(event, context):
    # ── 1. Extract caller identity from Cognito ───────────────
    claims = event["identity"]["claims"]
    requester_id = claims["sub"]
    requester_username = claims["cognito:username"]

    target_user_id = event["arguments"]["targetUserId"]

    # ── 2. Authorization check ────────────────────────────────
    # A user cannot follow themselves
    if requester_id == target_user_id:
        raise Exception("CANNOT_FOLLOW_SELF")

    # ── 3. Check target user actually exists ──────────────────
    target_resp = user_table.get_item(
        Key={"PK": f"USER#{target_user_id}", "SK": "PROFILE"}
    )
    if "Item" not in target_resp:
        raise Exception("TARGET_USER_NOT_FOUND")

    target_user = target_resp["Item"]
    now = datetime.now(timezone.utc).isoformat()

    # ── 4. Check for existing follow/request ─────────────────
    existing = follow_table.get_item(
        Key={
            "PK": f"USER#{requester_id}",
            "SK": f"FOLLOWS#{target_user_id}",
        }
    )
    if "Item" in existing:
        raise Exception("FOLLOW_ALREADY_EXISTS")

    # ── 5. Write follow record (single table, two items) ──────
    # Item 1: requester's outgoing follow  (for getMyFollowings)
    # Item 2: target's incoming follow     (for getMyFollowers via GSI)


    
    # fetch requester's own profile to get username
    requester_resp = user_table.get_item(
        Key={"PK": f"USER#{requester_id}", "SK": "PROFILE"}
    )

    requester_username_stored = requester_resp.get("Item", {}).get("username", requester_username)

    with follow_table.batch_writer() as batch:
        batch.put_item(Item={
            "PK": f"USER#{requester_id}",
            "SK": f"FOLLOWS#{target_user_id}",
            "GSI_PK": f"USER#{target_user_id}",
            "GSI_SK": f"FOLLOWER#{requester_id}",
            "requesterId": requester_id,
            "requesterUsername": requester_username_stored,   # ← added
            "targetId": target_user_id,
            "targetUsername": target_user["username"],        # ← added
            "status": "PENDING",
            "createdAt": now,
            "entityType": "FOLLOW",
        })
    # ── 6. Publish event to SQS for async notification ────────
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({
            "eventType": "FOLLOW_REQUEST",
            "recipientId": target_user_id,
            "senderId": requester_id,
            "senderUsername": requester_username,
            "message": f"{requester_username} sent you a follow request",
        }),
    )

    return {
        "userId": target_user_id,
        "username": target_user["username"],
        "status": "PENDING",
        "createdAt": now,
    }