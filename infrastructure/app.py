#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.cognito_stack import CognitoStack
from stacks.dynamodb_stack import DynamoDBStack
from stacks.appsync_stack import AppSyncStack
from stacks.sqs_lambda_stack import SqsLambdaStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1"
)

dynamodb_stack = DynamoDBStack(app, "SocialGraphDynamoDB", env=env)

cognito_stack = CognitoStack(
    app, "SocialGraphCognito",
    user_table=dynamodb_stack.user_table,
    env=env,
)

# ── SQS stack created BEFORE AppSync so we can pass the queue in ──
sqs_lambda_stack = SqsLambdaStack(
    app, "SocialGraphSqsLambda",
    notification_table=dynamodb_stack.notification_table,
    follow_table=dynamodb_stack.follow_table,
    env=env,
)

appsync_stack = AppSyncStack(
    app, "SocialGraphAppSync",
    user_pool=cognito_stack.user_pool,
    user_table=dynamodb_stack.user_table,
    follow_table=dynamodb_stack.follow_table,
    notification_table=dynamodb_stack.notification_table,
    notification_queue=sqs_lambda_stack.notification_queue,  # ← passed in
    env=env,
)


# checking by dwleteing this : problamatic code
# # AppSync API url needed by notification processor
# sqs_lambda_stack.notification_processor_fn.add_environment(
#     "APPSYNC_API_URL", 
#     appsync_stack.api.graphql_url
# )

app.synth()