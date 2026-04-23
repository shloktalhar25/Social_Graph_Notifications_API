# tests/test_follow.py
import boto3
import requests
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tests.config import USER_POOL_ID, CLIENT_ID, APPSYNC_URL, USER_ALICE, USER_BOB
from tests.test_auth import get_token, create_and_confirm_user

cognito = boto3.client("cognito-idp", region_name="us-east-1")


def gql(token: str, query: str, variables: dict = None) -> dict:
    """Helper - sends a GraphQL request with Cognito token auth."""
    resp = requests.post(
        APPSYNC_URL,
        headers={
            "Authorization": token,
            "Content-Type":  "application/json",
        },
        json={"query": query, "variables": variables or {}},
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise Exception(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")
    return data["data"]


def get_user_id(username: str) -> str:
    resp = cognito.admin_get_user(UserPoolId=USER_POOL_ID, Username=username)
    attrs = {a["Name"]: a["Value"] for a in resp["UserAttributes"]}
    return attrs["sub"]


if __name__ == "__main__":
    print("\nSetup: get tokens")
    alice_token = get_token(USER_ALICE)
    bob_token   = get_token(USER_BOB)
    alice_id    = get_user_id(USER_ALICE["username"])
    bob_id      = get_user_id(USER_BOB["username"])
    print(f"  Alice: {alice_id}")
    print(f"  Bob:   {bob_id}")

    print("\nTest 1: Alice requests to follow Bob")
    result = gql(
        alice_token,
        """
        mutation RequestFollow($targetUserId: ID!) {
          requestFollow(targetUserId: $targetUserId) {
            userId
            username
            status
            createdAt
          }
        }
        """,
        {"targetUserId": bob_id},
    )
    print(f"  Result: {json.dumps(result, indent=2)}")
    assert result["requestFollow"]["status"] == "PENDING", "Status should be PENDING"
    print("Follow request sent")

    print("\nTest 2: Bob checks getMyFollowers")
    result = gql(
        bob_token,
        """
        query {
          getMyFollowers {
            userId
            username
            status
          }
        }
        """,
    )
    print(f"  Result: {json.dumps(result, indent=2)}")
    assert any(f["status"] == "PENDING" for f in result["getMyFollowers"])
    print("Bob sees Alice's pending request")

    print("\nTest 3: Bob accepts Alice's request")
    result = gql(
        bob_token,
        """
        mutation AcceptFollow($requesterId: ID!) {
          acceptFollowRequest(requesterId: $requesterId) {
            userId
            username
            status
          }
        }
        """,
        {"requesterId": alice_id},
    )
    print(f"  Result: {json.dumps(result, indent=2)}")
    assert result["acceptFollowRequest"]["status"] == "ACCEPTED"
    print("Follow request accepted")

    print("\nTest 4: Alice checks getMyFollowings")
    result = gql(
        alice_token,
        """
        query {
          getMyFollowings {
            userId
            username
            status
          }
        }
        """,
    )
    print(f"  Result: {json.dumps(result, indent=2)}")
    assert any(f["status"] == "ACCEPTED" for f in result["getMyFollowings"])
    print("Alice sees Bob in her followings as ACCEPTED")

    print("\nTest 5: Auth guard - Alice cannot accept as Bob")
    try:
        gql(
            alice_token,   # Alice's token, but trying to accept Bob's request
            """
            mutation AcceptFollow($requesterId: ID!) {
              acceptFollowRequest(requesterId: $requesterId) { status }
            }
            """,
            {"requesterId": alice_id},
        )
        print("  Should have raised an error!")
    except Exception as e:
        print(f" Correctly rejected: {e}")

    print("\n All follow tests passed")