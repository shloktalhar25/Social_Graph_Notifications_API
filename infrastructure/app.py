#!/usr/bin/env python3
import aws_cdk as cdk
import aws_cdk.aws_iam as iam
from stacks.cognito_stack import CognitoStack
from stacks.dynamodb_stack import DynamoDBStack
from stacks.appsync_stack import AppSyncStack
from stacks.sqs_lambda_stack import SqsLambdaStack
from stacks.opensearch_stack import OpenSearchStack
from stacks.search_stack import SearchStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1",
)

dynamodb_stack   = DynamoDBStack(app, "SocialGraphDynamoDB", env=env)
opensearch_stack = OpenSearchStack(app, "SocialGraphOpenSearch", env=env)

cognito_stack = CognitoStack(
    app, "SocialGraphCognito",
    user_table=dynamodb_stack.user_table,
    env=env,
)

search_stack = SearchStack(
    app, "SocialGraphSearch",
    follow_table=dynamodb_stack.follow_table,
    opensearch_domain=opensearch_stack.domain,
    user_table=dynamodb_stack.user_table,
    env=env,
)

# Queue lives inside AppSyncStack - no cross-stack SQS reference
appsync_stack = AppSyncStack(
    app, "SocialGraphAppSync",
    user_pool=cognito_stack.user_pool,
    user_table=dynamodb_stack.user_table,
    follow_table=dynamodb_stack.follow_table,
    notification_table=dynamodb_stack.notification_table,
    search_fn=search_stack.search_fn,
    env=env,
)

# SqsLambdaStack receives the queue from AppSyncStack (one direction only)
sqs_lambda_stack = SqsLambdaStack(
    app, "SocialGraphSqsLambda",
    notification_table=dynamodb_stack.notification_table,
    follow_table=dynamodb_stack.follow_table,
    notification_queue=appsync_stack.notification_queue,
    env=env,
)

# Inject AppSync URL into processor - string reference, no CDK dependency
sqs_lambda_stack.notification_processor_fn.add_environment(
    "APPSYNC_API_URL", appsync_stack.api.graphql_url
)

# Grant processor permission to call createNotification via IAM
sqs_lambda_stack.notification_processor_fn.add_to_role_policy(
    iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        actions=["appsync:GraphQL"],
        resources=[
            cdk.Arn.format(
                cdk.ArnComponents(
                    service="appsync",
                    resource="apis",
                    resource_name=f"{appsync_stack.api_id}/types/Mutation/fields/createNotification",
                    arn_format=cdk.ArnFormat.SLASH_RESOURCE_NAME,
                ),
                appsync_stack,   # use appsync_stack as scope for correct region/account
            )
        ],
    )
)

app.synth()