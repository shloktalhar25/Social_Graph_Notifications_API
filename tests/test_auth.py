# tests/test_auth.py
import boto3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tests.config import USER_POOL_ID, CLIENT_ID, USER_ALICE, USER_BOB

cognito = boto3.client("cognito-idp", region_name="us-east-1")


def create_and_confirm_user(user: dict) -> str:
    """
    Creates a Cognito user and admin-confirms them
    (skips email verification for testing).
    Returns the user's Cognito sub (userId).
    """
    try:
        # Register
        cognito.sign_up(
            ClientId=CLIENT_ID,
            Username=user["username"],
            Password=user["password"],
            UserAttributes=[
                {"Name": "email", "Value": user["email"]},
                {"Name": "name",  "Value": user["username"]},
            ],
        )
        print(f"  Created user: {user['username']}")
    except cognito.exceptions.UsernameExistsException:
        print(f"  User already exists: {user['username']}")

    # Admin confirm - bypasses email verification
    cognito.admin_confirm_sign_up(
        UserPoolId=USER_POOL_ID,
        Username=user["username"],
    )
    print(f"  Confirmed user: {user['username']}")

    # Fetch sub (userId)
    resp = cognito.admin_get_user(
        UserPoolId=USER_POOL_ID,
        Username=user["username"],
    )
    attrs = {a["Name"]: a["Value"] for a in resp["UserAttributes"]}
    sub = attrs["sub"]
    print(f"  userId (sub): {sub}")
    return sub


def get_token(user: dict) -> str:
    """Authenticate and return the Cognito ID token."""
    resp = cognito.initiate_auth(
        ClientId=CLIENT_ID,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": user["username"],
            "PASSWORD": user["password"],
        },
    )
    return resp["AuthenticationResult"]["IdToken"]


if __name__ == "__main__":
    print("\nCreating test users")
    alice_id = create_and_confirm_user(USER_ALICE)
    bob_id   = create_and_confirm_user(USER_BOB)

    print("\nGetting tokens")
    

    alice_token = get_token(USER_ALICE)
    bob_token   = get_token(USER_BOB)

    print(f"\n  {USER_ALICE['username']} token (truncated): {alice_token[:40]}...")
    print(f"  {USER_BOB['username']} token (truncated): {bob_token[:40]}...")

    print(f"\n  {USER_ALICE['username']} userId: {alice_id}")
    print(f"  {USER_BOB['username']} userId: {bob_id}")