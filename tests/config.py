# contains all configuration values used for testing


# tests/config.py
# Paste your cdk deploy output values here

USER_POOL_ID      = "us-east-1_XXXXXXXXX"
CLIENT_ID         = "XXXXXXXXXXXXXXXXXXXXXXXXXX"
APPSYNC_URL       = "https://XXXXXX.appsync-api.us-east-1.amazonaws.com/graphql"

# Test users - we'll create these in test_auth.py
USER_ALICE = {"username": "alice", "password": "TestPassword123!", "email": "alice@example.com"}
USER_BOB   = {"username": "bob", "password": "TestPassword123!", "email": "bob@example.com"}