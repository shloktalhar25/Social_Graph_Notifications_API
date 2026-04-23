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

## Step 1 — Clone and set up the environment

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

## Step 2 — Install Lambda dependencies

Lambda functions require Python packages bundled locally (no Docker needed):

```bash
pip install requests requests-aws4auth -t functions/notification_processor/
pip install opensearch-py requests-aws4auth -t functions/opensearch_sync/
pip install opensearch-py requests-aws4auth -t functions/search_resolver/
```

---

## Step 3 — Bootstrap CDK

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

## Step 4 — Deploy all stacks

```bash
cdk deploy --all --require-approval never
```

> This takes approximately 20 minutes. OpenSearch domain provisioning is the slow step.

At the end of deployment, note these output values — you will need them in Step 5:

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

## Step 5 — Configure tests

Open `tests/config.py` and fill in the values from Step 4:

```python
USER_POOL_ID = "us-east-1_XXXXXXXXX"      # from SocialGraphCognito outputs
CLIENT_ID    = "XXXXXXXXXXXXXXXXXX"         # from SocialGraphCognito outputs
APPSYNC_URL  = "https://XXXX.appsync-api.us-east-1.amazonaws.com/graphql"

REGION = "us-east-1"

# Test user credentials — these will be created fresh
USER_ALICE = {"username": "alice", "password": "Test1234!", "email": "alice@example.com"}
USER_BOB   = {"username": "bob",   "password": "Test1234!", "email": "bob@example.com"}
```

> If `alice` or `bob` already exist in the User Pool from a previous run, either
> change the usernames or delete them via the Cognito console before running tests.

---

## Step 6 — Run the test suite

Run each script in this exact order:

### 6a. Create and confirm test users
```bash
python tests/test_auth.py
```

Expected output:
```
── Creating test users ──────────────────────
  Created user: alice
  Confirmed user: alice
  userId (sub): xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Created user: bob
  Confirmed user: bob
  userId (sub): xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
✅ Auth setup complete
```

### 6b. Follow flow and authorization guards
```bash
python -m tests.test_follow
```

Expected output:
```
✅ Follow request sent
✅ Bob sees Alice's pending request
✅ Follow request accepted
✅ Alice sees Bob in her followings as ACCEPTED
✅ Correctly rejected  ← auth guard working
✅ All follow tests passed
```

### 6c. Async notification pipeline
```bash
python -m tests.test_notifications
```

Expected output:
```
✅ Bob received FOLLOW_REQUEST notification
✅ Alice received FOLLOW_ACCEPTED notification
✅ GraphQL notifications query works
✅ Bob only sees his own notifications
✅ All notification tests passed
```

> The test polls DynamoDB every 5 seconds for up to 30 seconds while waiting
> for the SQS → Lambda → AppSync pipeline to complete.

### 6d. OpenSearch search and auth isolation
```bash
python -m tests.test_search
```

Expected output:
```
✅ searchMyFollowers works
✅ searchMyFollowings works
✅ Auth isolation correct
✅ All search tests passed
```

> The test waits 15 seconds for the DynamoDB Streams → OpenSearch sync to complete.

---

## Step 7 — Verify in AWS Console (optional)

### DynamoDB
- `social-users` — should contain user records with `PK = USER#<id>`
- `social-follows` — should contain follow records; check `GSI-FollowerIndex` exists
- `social-notifications` — should contain notification records with `SK = NOTIF#<timestamp>#<uuid>`

### AppSync
- Go to AWS AppSync → APIs → `social-graph-api`
- Confirm authorization modes: Cognito User Pools (default) + IAM (additional)
- Go to Schema — confirm all types and mutations are present
- Go to Data sources — confirm 8 Lambda data sources are attached

### SQS
- `social-notifi-queue` — check Monitoring tab; NumberOfMessagesSent should match NumberOfMessagesDeleted (all consumed cleanly)
- `social-notif-dlq` — ApproximateNumberOfMessages should be 0 (no failed messages)

### OpenSearch
- Go to Amazon OpenSearch Service → Domains → `social-graph-search`
- Cluster health should show **Green**
- Instance count: 2 x t3.small.search

---

## Step 8 — Check Lambda logs (optional deep verification)

```bash
# Notification processor — confirm it called AppSync mutation
aws logs tail /aws/lambda/social-notification-processor --since 1h

# Look for lines like:
# Notification created via AppSync: FOLLOW_REQUEST for user <id>
# Notification created via AppSync: FOLLOW_ACCEPTED for user <id>

# OpenSearch sync Lambda — confirm it indexed follow records
aws logs tail /aws/lambda/social-dynamo-opensearch-sync --since 1h

# Look for lines like:
# Indexed doc: USER_xxx_FOLLOWS_xxx status=ACCEPTED

# Search resolver — confirm it executed OpenSearch queries
aws logs tail /aws/lambda/social-search-resolver --since 1h
```

---

## Step 9 — Teardown

When you are done evaluating, destroy all AWS resources:

```bash
cdk destroy --all
```

> OpenSearch domain deletion takes approximately 10 minutes.
> DynamoDB tables and Lambda functions are removed immediately.

---

## Project Structure

```
social-graph-api/
├── infrastructure/
│   ├── app.py                          # CDK entry point — stack wiring
│   └── stacks/
│       ├── cognito_stack.py            # Cognito User Pool + post-confirmation trigger
│       ├── dynamodb_stack.py           # 3 DynamoDB tables + GSI
│       ├── appsync_stack.py            # AppSync API + all Lambda resolvers + SQS queue
│       ├── sqs_lambda_stack.py         # Notification processor Lambda
│       ├── opensearch_stack.py         # OpenSearch 2-node domain
│       └── search_stack.py             # DynamoDB Streams sync + search resolver Lambda
├── functions/
│   ├── post_confirmation/              # Fires on Cognito signup → saves user to DynamoDB
│   ├── resolvers/
│   │   ├── request_follow/             # Mutation: send a follow request
│   │   ├── accept_follow/              # Mutation: accept a follow request
│   │   ├── get_followers/              # Query: users who follow me (queries GSI)
│   │   ├── get_followings/             # Query: users I follow (queries base table)
│   │   ├── get_notifications/          # Query: my notifications
│   │   └── create_notification/        # Mutation: IAM-only, called by notification processor
│   ├── notification_processor/         # SQS consumer → calls AppSync createNotification
│   ├── opensearch_sync/                # DynamoDB Streams → OpenSearch upsert/delete
│   └── search_resolver/                # Handles searchMyFollowers + searchMyFollowings
├── tests/
│   ├── config.py                       # ← fill this with your deploy output values
│   ├── test_auth.py
│   ├── test_follow.py
│   ├── test_notifications.py
│   └── test_search.py
├── schema.graphql                      # Full AppSync GraphQL schema
├── cdk.json
└── requirements.txt
```

---

## Architectural Decisions

### 1. AWS CDK (Python) over Amplify CLI

Amplify Gen 2 is TypeScript-only for infrastructure. CDK gives full control over IAM policies, resolver wiring, SQS, and OpenSearch — all of which this project needs explicit configuration for.

### 2. DynamoDB access pattern — adjacency list with GSI

The follow relationship is written as one item with dual key sets:

```
Base table:  PK = USER#<requesterId>   SK = FOLLOWS#<targetId>
GSI:         GSI_PK = USER#<targetId>  GSI_SK = FOLLOWER#<requesterId>
```

`getMyFollowings` queries the base table. `getMyFollowers` queries the GSI. Both directions are O(n) key lookups with no scans.

### 3. Authorization enforced in resolvers — not just @auth

`@aws_cognito_user_pools` only checks that the caller is authenticated. All deeper authorization is done manually in the Lambda resolvers:

- `acceptFollowRequest` fetches the follow record and checks that `targetId` matches the caller's Cognito `sub` before writing
- `getMyFollowers`, `getMyFollowings`, `getMyNotifications` extract `sub` from claims and use it as the DynamoDB partition key — there is no user-supplied `userId` argument that could be forged
- OpenSearch queries inject the caller's `sub` as a hard `MUST` clause — impossible to bypass via arguments

### 4. SQS async notification pipeline

Mutations publish to SQS and return immediately. A downstream Lambda consumes the queue and calls the `createNotification` AppSync mutation via IAM-signed HTTP. Calling through AppSync (rather than writing DynamoDB directly) fires the `onNewNotification` subscription for real-time delivery.

Messages retry 3 times on failure before moving to a Dead Letter Queue (DLQ).

### 5. OpenSearch — 2 nodes, zone awareness, 1 replica

Two `t3.small.search` nodes across 2 AZs with `number_of_replicas: 1`. Each primary shard has one replica on the other node — this is the minimum configuration that achieves green cluster health.

DynamoDB Streams trigger the sync Lambda on INSERT, MODIFY, and REMOVE. `bisect_batch_on_error=True` isolates bad records so one failure never blocks the rest of the batch.

### 6. Stack dependency management

The SQS queue lives inside `AppSyncStack` alongside the resolver Lambdas that publish to it. `SqsLambdaStack` receives the queue as a parameter. This ensures the dependency is one-directional and eliminates any circular reference between stacks.

---

## Trade-offs and Known Limitations

| Area | Detail |
|---|---|
| Subscriptions | `onFollowAccepted` and `onNewNotification` are defined in the schema and will fire when mutations are called. Not tested with a WebSocket client in the automated suite. |
| Pagination | Queries return up to 50 items. Production would use DynamoDB `LastEvaluatedKey` and OpenSearch `search_after` for cursor pagination. |
| SQS idempotency | Standard queues deliver at-least-once. A conditional write (`attribute_not_exists`) on the notification table would make processing fully idempotent. |
| Username changes | Usernames are denormalized into follow records at write time. Changing a username would require a backfill job. |
| No unfollow / reject | Follow request accept is supported. Unfollow and reject follow the same pattern and are straightforward additions. |
| Single region | Multi-region would require DynamoDB Global Tables and replicating the OpenSearch domain. |
