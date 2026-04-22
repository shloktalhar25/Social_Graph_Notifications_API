# Social Graph & Notifications API

A production-oriented GraphQL backend for a social application built on AWS. Supports user management, a bidirectional follow system with request/accept flow, and an asynchronous real-time notification pipeline.

---

## Stack

| Layer | Service |
|---|---|
| API | AWS AppSync (GraphQL) |
| Auth | Amazon Cognito User Pools |
| Database | Amazon DynamoDB (single-table design per domain) |
| Async processing | Amazon SQS + AWS Lambda |
| Infrastructure | AWS CDK (Python) |
| Runtime | Python 3.10 |

---

## Project Structure

```
social-graph-api/
├── infrastructure/
│   ├── app.py                        # CDK entry point
│   └── stacks/
│       ├── cognito_stack.py          # User Pool + post-confirmation trigger
│       ├── dynamodb_stack.py         # All DynamoDB tables + GSI
│       ├── appsync_stack.py          # GraphQL API + Lambda resolvers
│       └── sqs_lambda_stack.py       # Queue + notification processor
├── functions/
│   ├── post_confirmation/            # Cognito trigger → persists user profile
│   ├── resolvers/
│   │   ├── request_follow/           # Mutation: send follow request
│   │   ├── accept_follow/            # Mutation: accept follow request
│   │   ├── get_followers/            # Query: who follows me
│   │   ├── get_followings/           # Query: who I follow
│   │   └── get_notifications/        # Query: my notifications
│   └── notification_processor/       # SQS consumer → writes notifications
├── tests/
│   ├── config.py                     # Deployment output values
│   ├── test_auth.py                  # User creation + Cognito tokens
│   ├── test_follow.py                # Follow flow + auth guards
│   └── test_notifications.py         # Async notification pipeline
├── schema.graphql                    # AppSync GraphQL schema
├── cdk.json
└── requirements.txt
```

---

## Prerequisites

- Python 3.10
- Node.js v18+ (for CDK CLI)
- AWS CLI v2 configured (`aws configure`)
- AWS CDK CLI (`npm install -g aws-cdk`)

---

## Deploy

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd social-graph-api

# 2. Create and activate virtualenv
python3.10 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Bootstrap CDK (once per account/region)
cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-1

# 5. Deploy all stacks
cdk deploy --all --require-approval never
```

After deploy, note the printed outputs:

```
SocialGraphCognito.UserPoolId         = us-east-1_XXXXXXXX
SocialGraphCognito.UserPoolClientId   = XXXXXXXXXXXXXXXXXX
SocialGraphAppSync.GraphQLApiUrl      = https://XXXX.appsync-api.us-east-1.amazonaws.com/graphql
SocialGraphSqsLambda.NotificationQueueUrl = https://sqs...
```

---

## Test

Paste the deploy output values into `tests/config.py`, then run in order:

```bash
# 1. Create and confirm Cognito test users
python tests/test_auth.py

# 2. Test the full follow flow + authorization guards
python tests/test_follow.py

# 3. Test async notification pipeline + GraphQL query
python tests/test_notifications.py
```

### What the tests verify

| Test | What it checks |
|---|---|
| `test_auth.py` | Cognito signup → DynamoDB user record via post-confirmation trigger |
| `test_follow.py` Test 1 | `requestFollow` mutation creates PENDING record |
| `test_follow.py` Test 2 | `getMyFollowers` returns correct result via GSI |
| `test_follow.py` Test 3 | `acceptFollowRequest` updates status to ACCEPTED |
| `test_follow.py` Test 4 | `getMyFollowings` returns correct result via base table |
| `test_follow.py` Test 5 | Auth guard rejects a user accepting a request not meant for them |
| `test_notifications.py` Tests 1–2 | SQS → Lambda → DynamoDB notification written correctly |
| `test_notifications.py` Test 3 | `getMyNotifications` GraphQL query returns correct records |
| `test_notifications.py` Test 4 | Users can only read their own notifications |

---

## Teardown

```bash
cdk destroy --all
```

---

## Architectural Decisions

### 1. AWS CDK (Python) over Amplify CLI

Amplify Gen 2 requires TypeScript for infrastructure. Since the project is Python-first and needs full control over IAM policies, resolver wiring, and SQS configuration, CDK was the appropriate choice. It produces explicit, reviewable CloudFormation and allows precise scoping of every permission grant.

### 2. DynamoDB Access Pattern Design

The follow relationship needs to be queried efficiently in both directions:
- "Who follows me?" (incoming)
- "Who do I follow?" (outgoing)

A single write to one item would make one direction expensive (requiring a scan or filter). Instead, each follow record is written with both base-table keys and GSI keys in the same item:

```
Base table:  PK = USER#<requesterId>   SK = FOLLOWS#<targetId>
GSI:         GSI_PK = USER#<targetId>  GSI_SK = FOLLOWER#<requesterId>
```

`getMyFollowings` queries the base table. `getMyFollowers` queries the GSI. Both are O(n) key queries with no scans.

### 3. Authorization Beyond @auth

The task explicitly requires that authorization logic beyond "is the user authenticated" be enforced manually in resolvers. Two examples of this in the codebase:

**`acceptFollowRequest`** — After fetching the follow record from DynamoDB, the resolver inspects the `targetId` field and compares it to the caller's Cognito `sub`. If they don't match, it raises `UNAUTHORIZED` before any write occurs. The `@aws_cognito_user_pools` directive only ensures the caller is authenticated — it cannot enforce that the caller is the intended recipient.

**`getMyFollowers` / `getMyFollowings` / `getMyNotifications`** — All three resolvers extract `sub` from the Cognito identity claims and use it directly as the DynamoDB partition key. Users have no parameter to pass — they always get their own data. This is safer than accepting a `userId` argument which a user could forge.

### 4. Asynchronous Notification Processing via SQS

Mutations (`requestFollow`, `acceptFollowRequest`) do not create notification records inline. Instead they publish a lightweight JSON event to an SQS standard queue. A downstream Lambda consumes the queue and writes to DynamoDB.

**Why:** Keeps mutation latency low and decouples notification logic from business logic. If the notification processor fails, the mutation has already succeeded. Messages retry up to 3 times before moving to a Dead Letter Queue (DLQ), giving visibility into processing failures without data loss.

### 5. Notification Processor Writes DynamoDB Directly (Not via AppSync)

The Lambda processor writes notifications directly to DynamoDB using IAM-scoped credentials rather than calling the AppSync `createNotification` mutation.

**Why:** Calling AppSync from Lambda adds an unnecessary HTTP hop, requires managing endpoint URLs, and introduces another failure point. Direct DynamoDB writes are faster, simpler, and the IAM grant is already tightly scoped to only the notification table. The `createNotification` mutation is still defined in the schema with `@aws_iam` so it can trigger AppSync subscriptions for real-time delivery.

### 6. Subscription Authorization

Both subscriptions (`onFollowAccepted`, `onNewNotification`) require the caller to pass their own `userId` as a filter argument. AppSync enforces that the subscription argument matches the caller's Cognito identity — users cannot subscribe to another user's events.

---

## Trade-offs and Known Limitations

| Area | Trade-off / Limitation |
|---|---|
| Username denormalization | Usernames are stored in follow records at write time. If a user changes their username, existing follow records will show the old name. A production system would either prohibit username changes or run an async update job. |
| No pagination | `getMyFollowers`, `getMyFollowings`, and `getMyNotifications` return up to 50 items. A production API would use DynamoDB's `LastEvaluatedKey` for cursor-based pagination. |
| Standard SQS queue | Messages may be delivered more than once (at-least-once delivery). The notification processor does not currently implement idempotency checks. A `notificationId` is generated per message — adding a conditional write (`attribute_not_exists(PK)`) would make it fully idempotent. |
| No unfollow mutation | The follow system supports request and accept but not unfollow or reject. These are straightforward additions following the same pattern. |
| Test users require admin confirmation | Tests use `admin_confirm_sign_up` to bypass email verification. Real users go through the standard email confirmation flow which triggers the post-confirmation Lambda identically. |
| Single region | The stack deploys to one region. Multi-region would require DynamoDB Global Tables and additional CDK configuration. |
