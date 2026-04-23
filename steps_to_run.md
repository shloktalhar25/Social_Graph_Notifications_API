# Social Graph & Notifications API

A production-oriented GraphQL backend for a social application built on AWS.
Supports user management, a bidirectional follow system, asynchronous notifications,
and full-text search powered by Amazon OpenSearch Service.

---

## Stack

| Layer | Service |
|---|---|
| API | AWS AppSync (GraphQL) |
| Auth | Amazon Cognito User Pools |
| Database | Amazon DynamoDB |
| Search | Amazon OpenSearch Service |
| Async processing | Amazon SQS + AWS Lambda |
| Infrastructure | AWS CDK (Python) |
| Runtime | Python 3.10 |

---

## Prerequisites

Make sure the following are installed and configured before starting:

| Tool | Version | Check |
|---|---|---|
| Python | 3.10+ | `python --version` |
| Node.js | v18+ | `node --version` |
| AWS CLI | v2 | `aws --version` |
| AWS CDK CLI | latest | `cdk --version` |

Install CDK CLI if not present:
```bash
npm install -g aws-cdk
```

Configure AWS credentials:
```bash
aws configure
# Enter: Access Key ID, Secret Access Key, region (us-east-1), output (json)
```

Verify credentials work:
```bash
aws sts get-caller-identity
```

---

## Step 1 - Clone and set up the environment

```bash
git clone <repo-url>
cd social-graph-api

# Create and activate Python virtual environment
python3.10 -m venv .venv

# Mac/Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate

# Install infrastructure dependencies
pip install -r requirements.txt
```

---

## Step 2 - Install Lambda dependencies

Lambda functions require Python packages bundled locally (no Docker needed):

```bash
pip install requests requests-aws4auth -t functions/notification_processor/
pip install opensearch-py requests-aws4auth -t functions/opensearch_sync/
pip install opensearch-py requests-aws4auth -t functions/search_resolver/
```

---

## Step 3 - Bootstrap CDK

These are one-time setup commands per AWS account:

```bash
# Create OpenSearch service-linked role (ignore error if it already exists)
aws iam create-service-linked-role --aws-service-name es.amazonaws.com

# Get your AWS account ID
aws sts get-caller-identity --query Account --output text

# Bootstrap CDK (replace ACCOUNT_ID with the value above)
cdk bootstrap aws://ACCOUNT_ID/us-east-1
```

---

## Step 4 - Deploy all stacks

```bash
cdk deploy --all --require-approval never
```

> This takes approximately 20 minutes. OpenSearch domain provisioning is the slow step.

At the end of deployment, note these output values - you will need them in Step 5:

```
SocialGraphCognito.UserPoolId        = us-east-1_XXXXXXXXX
SocialGraphCognito.UserPoolClientId  = XXXXXXXXXXXXXXXXXX
SocialGraphAppSync.GraphQLApiUrl     = https://XXXX.appsync-api.us-east-1.amazonaws.com/graphql
```

If you missed them, retrieve them with:
```bash
aws cloudformation describe-stacks --stack-name SocialGraphCognito \
  --query "Stacks[0].Outputs" --output table

aws cloudformation describe-stacks --stack-name SocialGraphAppSync \
  --query "Stacks[0].Outputs[?OutputKey=='GraphQLApiUrl'].OutputValue" --output text
```

---

## Step 5 - Configure tests

Open `tests/config.py` and fill in the values from Step 4:

```python
USER_POOL_ID = "us-east-1_XXXXXXXXX"      # from SocialGraphCognito outputs
CLIENT_ID    = "XXXXXXXXXXXXXXXXXX"         # from SocialGraphCognito outputs
APPSYNC_URL  = "https://XXXX.appsync-api.us-east-1.amazonaws.com/graphql"

REGION = "us-east-1"

# Test user credentials - these will be created fresh
USER_ALICE = {"username": "alice", "password": "Test1234!", "email": "alice@example.com"}
USER_BOB   = {"username": "bob",   "password": "Test1234!", "email": "bob@example.com"}
```

---

## Step 6 - Run the test suite

Run each script in this exact order:

### 6a. Create and confirm test users
```bash
python tests/test_auth.py
```

Expected output:
```
  Created user: alice
  Confirmed user: alice
  userId (sub): xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Created user: bob
  Confirmed user: bob
  userId (sub): xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Auth setup complete
```

### 6b. Follow flow and authorization guards
```bash
python -m tests.test_follow
```

Expected output:
```
Follow request sent
Bob sees Alice's pending request
Follow request accepted
Alice sees Bob in her followings as ACCEPTED
Correctly rejected  <- auth guard working
All follow tests passed
```

### 6c. Async notification pipeline
```bash
python -m tests.test_notifications
```

Expected output:
```
Bob received FOLLOW_REQUEST notification
Alice received FOLLOW_ACCEPTED notification
GraphQL notifications query works
Bob only sees his own notifications
All notification tests passed
```

### 6d. OpenSearch search and auth isolation
```bash
python -m tests.test_search
```

Expected output:
```
searchMyFollowers works
searchMyFollowings works
Auth isolation correct
All search tests passed
```

---

## Step 7 - Verify in AWS Console (optional)

### DynamoDB
- `social-users` - should contain user records with `PK = USER#<id>`
- `social-follows` - should contain follow records; check `GSI-FollowerIndex` exists
- `social-notifications` - should contain notification records with `SK = NOTIF#<timestamp>#<uuid>`

### AppSync
- Go to AWS AppSync -> APIs -> `social-graph-api`
- Confirm authorization modes: Cognito User Pools (default) + IAM (additional)
- Go to Schema - confirm all types and mutations are present
- Go to Data sources - confirm 8 Lambda data sources are attached

### SQS
- `social-notifi-queue` - check Monitoring tab; NumberOfMessagesSent should match NumberOfMessagesDeleted
- `social-notif-dlq` - ApproximateNumberOfMessages should be 0

### OpenSearch
- Go to Amazon OpenSearch Service -> Domains -> `social-graph-search`
- Cluster health should show Green
- Instance count: 2 x t3.small.search

---

## Step 8 - Check Lambda logs

```bash
# Notification processor - confirm it called AppSync mutation
aws logs tail /aws/lambda/social-notification-processor --since 1h

# OpenSearch sync Lambda - confirm it indexed follow records
aws logs tail /aws/lambda/social-dynamo-opensearch-sync --since 1h

# Search resolver - confirm it executed OpenSearch queries
aws logs tail /aws/lambda/social-search-resolver --since 1h
```

---

## Step 9 - Teardown

```bash
cdk destroy --all
```

---

## Project Structure

```
social-graph-api/
+-- infrastructure/
|   +-- app.py
|   `-- stacks/
|       +-- cognito_stack.py
|       +-- dynamodb_stack.py
|       +-- appsync_stack.py
|       +-- sqs_lambda_stack.py
|       +-- opensearch_stack.py
|       `-- search_stack.py
+-- functions/
|   +-- post_confirmation/
|   +-- resolvers/
|   |   +-- request_follow/
|   |   +-- accept_follow/
|   |   +-- get_followers/
|   |   +-- get_followings/
|   |   +-- get_notifications/
|   |   `-- create_notification/
|   +-- notification_processor/
|   +-- opensearch_sync/
|   `-- search_resolver/
+-- tests/
|   +-- config.py
|   +-- test_auth.py
|   +-- test_follow.py
|   +-- test_notifications.py
|   `-- test_search.py
+-- schema.graphql
+-- cdk.json
`-- requirements.txt
```

---

## Architectural Decisions

1. **AWS CDK (Python)**: Provides full control over IAM policies and AWS resources while staying in the Python ecosystem.
2. **DynamoDB Adjacency List**: Uses a single item with dual keys to index follow relationships in both directions efficiently.
3. **Lambda Authorizers**: Deep authorization checks (like verifying relationship ownership) are enforced in resolver logic.
4. **Asynchronous Notifications**: Uses SQS to decouple notification delivery from core mutations, reducing latency.
5. **OpenSearch Sync**: Uses DynamoDB Streams for real-time indexing, enabling complex search patterns while maintaining DynamoDB as the source of truth.
