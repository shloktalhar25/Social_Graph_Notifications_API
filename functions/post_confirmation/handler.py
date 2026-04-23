import os
import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["USER_TABLE_NAME"])


def lambda_handler(event, context):
    """
    Fires after Cognito email confirmation.
    Saves the user profile to DynamoDB.
    """
    user_attrs = event["request"]["userAttributes"]

    user_id = user_attrs["sub"]          # Cognito's unique user ID
    email = user_attrs.get("email", "")
    username = event["userName"]
    full_name = user_attrs.get("name", "")
    now = datetime.now(timezone.utc).isoformat()

    table.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": "PROFILE",
            "userId": user_id,
            "username": username,
            "email": email,
            "fullName": full_name,
            "createdAt": now,
            "entityType": "USER",
        },
        # Don't overwrite if already exists (safety guard)
        ConditionExpression="attribute_not_exists(PK)",
    )

    # Must return the event unchanged - Cognito requires this
    return event