# verify SQS → Lambda → DynamoDB

import boto3
import requests
import json
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tests.config import USER_POOL_ID, CLIENT_ID, APPSYNC_URL, USER_ALICE, USER_BOB
from tests.test_auth import get_token
from tests.test_follow import gql

cognito  = boto3.client("cognito-idp", region_name="us-east-1")
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
notif_table = dynamodb.Table("social-notifications")


def get_user_id(username: str) -> str:
    resp = cognito.admin_get_user(UserPoolId=USER_POOL_ID, Username=username)
    attrs = {a["Name"]: a["Value"] for a in resp["UserAttributes"]}
    return attrs["sub"]


def poll_notifications(user_id: str, expected_type: str, retries=6, delay=5) -> dict:
    """
    Polls DynamoDB for a notification of the expected type.
    SQS → Lambda is async so we retry with a small delay.
    """
    for attempt in range(retries):
        resp = notif_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(
                f"USER#{user_id}"
            )
        )
        matches = [
            item for item in resp.get("Items", [])
            if item.get("type") == expected_type
        ]
        if matches:
            return matches[-1]
        print(f"  Attempt {attempt+1}/{retries} — not yet, waiting {delay}s...")
        time.sleep(delay)

    raise AssertionError(f"Notification of type {expected_type} not found after {retries} retries")


if __name__ == "__main__":
    print("\nSetup")
    alice_token = get_token(USER_ALICE)
    bob_token   = get_token(USER_BOB)
    alice_id    = get_user_id(USER_ALICE["username"])
    bob_id      = get_user_id(USER_BOB["username"])

    print("\nTest 1: Bob gets FOLLOW_REQUEST notification")
    print("  Waiting for SQS → Lambda → DynamoDB...")
    notif = poll_notifications(bob_id, "FOLLOW_REQUEST")
    print(f"  Notification: {json.dumps(notif, indent=2, default=str)}")
    assert notif["senderId"] == alice_id
    assert notif["read"] == False
    print("Bob received FOLLOW_REQUEST notification")

    print("\nTest 2: Alice gets FOLLOW_ACCEPTED notification")
    print("  Waiting for SQS → Lambda → DynamoDB...")
    notif = poll_notifications(alice_id, "FOLLOW_ACCEPTED")
    print(f"  Notification: {json.dumps(notif, indent=2, default=str)}")
    assert notif["senderId"] == bob_id
    print("Alice received FOLLOW_ACCEPTED notification")

    print("\nTest 3: Alice fetches notifications via GraphQL")
    result = gql(
        alice_token,
        """
        query {
          getMyNotifications {
            notificationId
            type
            message
            senderUsername
            read
            createdAt
          }
        }
        """,
    )
    notifs = result["getMyNotifications"]
    print(f"  Found {len(notifs)} notification(s)")
    print(f"  Latest: {json.dumps(notifs[0], indent=2)}")
    assert len(notifs) >= 1
    assert any(n["type"] == "FOLLOW_ACCEPTED" for n in notifs)
    print("GraphQL notifications query works")

    print("\nTest 4: Bob cannot read Alice's notifications")
    # Bob's token queries getMyNotifications
    # He should only see HIS OWN — not Alice's
    result = gql(
        bob_token,
        "query { getMyNotifications { notificationId type recipientId } }",
    )
    for n in result["getMyNotifications"]:
        assert n["recipientId"] == bob_id, \
            f" Bob received someone else's notification! {n}"
    print("Bob only sees his own notifications")

    print("\n All notification tests passed")