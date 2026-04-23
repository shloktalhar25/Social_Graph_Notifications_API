import time
import boto3
from tests.test_auth import get_token
from tests.test_follow import gql
from tests.config import USER_ALICE, USER_BOB, USER_POOL_ID

cognito = boto3.client("cognito-idp", region_name="us-east-1")


def get_user_id(username: str) -> str:
    resp = cognito.admin_get_user(UserPoolId=USER_POOL_ID, Username=username)
    attrs = {a["Name"]: a["Value"] for a in resp["UserAttributes"]}
    return attrs["sub"]


if __name__ == "__main__":
    print("\nSetup")
    alice_token = get_token(USER_ALICE)
    bob_token   = get_token(USER_BOB)
    alice_id    = get_user_id(USER_ALICE["username"])
    bob_id      = get_user_id(USER_BOB["username"])
    print(f"  Alice: {alice_id}")
    print(f"  Bob:   {bob_id}")

    print("\nWaiting 15s for stream sync...")
    time.sleep(15)

    print("\nTest 1: Bob searches his followers")
    result = gql(
        bob_token,
        """
        query Search($term: String!) {
          searchMyFollowers(searchTerm: $term) {
            userId username status
          }
        }
        """,
        {"term": USER_ALICE["username"]},
    )
    print(f"  Result: {result}")
    assert len(result["searchMyFollowers"]) > 0, \
        f"Expected followers, got empty. Alice={alice_id} Bob={bob_id}"
    assert result["searchMyFollowers"][0]["userId"] == alice_id
    print("  searchMyFollowers works")

    print("\nTest 2: Alice searches her followings")
    result = gql(
        alice_token,
        """
        query Search($term: String!) {
          searchMyFollowings(searchTerm: $term) {
            userId username status
          }
        }
        """,
        {"term": USER_BOB["username"]},
    )
    print(f"  Result: {result}")
    assert len(result["searchMyFollowings"]) > 0, \
        f"Expected followings, got empty. Alice={alice_id} Bob={bob_id}"
    assert result["searchMyFollowings"][0]["userId"] == bob_id
    print("   searchMyFollowings works")

    print("\nTest 3: Auth isolation")
    result = gql(
        alice_token,
        """
        query Search($term: String!) {
          searchMyFollowers(searchTerm: $term) {
            userId username status
          }
        }
        """,
        {"term": ""},   # empty = match all, but scoped to Alice's followers only
    )
    for f in result["searchMyFollowers"]:
        assert f["userId"] != bob_id, \
            " Alice saw Bob in her followers — auth leak!"
    print("  Auth isolation correct")

    print("\n All search tests passed")