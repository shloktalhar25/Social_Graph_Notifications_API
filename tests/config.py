# contains all configuration values used for testing


# tests/config.py
# Paste your cdk deploy output values here

USER_POOL_ID      = "us-east-1_RIonAJLlF"
CLIENT_ID         = "38i0mtl70vtr8ij6ncavhgl2r1"
APPSYNC_URL       = "https://sjcpadj3dnbiznkmmf45egvnou.appsync-api.us-east-1.amazonaws.com/graphql"

# Test users — we'll create these in test_auth.py
USER_ALICE = {"username": "leanord", "password": "Test1234!", "email": "tim@example.com"}
USER_BOB   = {"username": "howard",   "password": "Test1234!", "email": "dawd@example.com"}