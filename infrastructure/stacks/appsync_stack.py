import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_appsync as appsync,
    aws_lambda as _lambda,
    aws_iam as iam,
    Duration,
)
from constructs import Construct


class AppSyncStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        user_pool,
        user_table,
        follow_table,
        notification_table,
        notification_queue,       # ← added: SQS queue reference
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Shared Lambda environment ─────────────────────────────────
        shared_env = {
            "USER_TABLE_NAME":          user_table.table_name,
            "FOLLOW_TABLE_NAME":        follow_table.table_name,
            "NOTIFICATION_TABLE_NAME":  notification_table.table_name,
            "NOTIFICATION_QUEUE_URL":   notification_queue.queue_url,
        }

        # ── AppSync API ───────────────────────────────────────────────
        self.api = appsync.GraphqlApi(
            self, "SocialGraphApi",
            name="social-graph-api",
            definition=appsync.Definition.from_file("schema.graphql"),
            authorization_config=appsync.AuthorizationConfig(
                default_authorization=appsync.AuthorizationMode(
                    authorization_type=appsync.AuthorizationType.USER_POOL,
                    user_pool_config=appsync.UserPoolConfig(
                        user_pool=user_pool,
                    ),
                ),
                additional_authorization_modes=[
                    appsync.AuthorizationMode(
                        authorization_type=appsync.AuthorizationType.IAM,
                    ),
                ],
            ),
            log_config=appsync.LogConfig(
                field_log_level=appsync.FieldLogLevel.ERROR,
            ),
            xray_enabled=True,
        )

        # ── Lambda Functions ──────────────────────────────────────────

        request_follow_fn = _lambda.Function(
            self, "RequestFollowFn",
            function_name="social-request-follow",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("functions/resolvers/request_follow"),
            timeout=Duration.seconds(15),
            environment=shared_env,
        )

        accept_follow_fn = _lambda.Function(
            self, "AcceptFollowFn",
            function_name="social-accept-follow",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("functions/resolvers/accept_follow"),
            timeout=Duration.seconds(15),
            environment=shared_env,
        )

        get_followers_fn = _lambda.Function(
            self, "GetFollowersFn",
            function_name="social-get-followers",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("functions/resolvers/get_followers"),
            timeout=Duration.seconds(15),
            environment=shared_env,
        )

        get_followings_fn = _lambda.Function(
            self, "GetFollowingsFn",
            function_name="social-get-followings",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("functions/resolvers/get_followings"),
            timeout=Duration.seconds(15),
            environment=shared_env,
        )

        get_notifications_fn = _lambda.Function(
            self, "GetNotificationsFn",
            function_name="social-get-notifications",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("functions/resolvers/get_notifications"),
            timeout=Duration.seconds(15),
            environment=shared_env,
        )

        # ── IAM Grants ────────────────────────────────────────────────

        # follow mutations need read+write on follow + user tables
        user_table.grant_read_data(request_follow_fn)
        follow_table.grant_read_write_data(request_follow_fn)
        notification_queue.grant_send_messages(request_follow_fn)

        user_table.grant_read_data(accept_follow_fn)
        follow_table.grant_read_write_data(accept_follow_fn)
        notification_queue.grant_send_messages(accept_follow_fn)

        # queries are read-only
        follow_table.grant_read_data(get_followers_fn)
        follow_table.grant_read_data(get_followings_fn)
        notification_table.grant_read_data(get_notifications_fn)

        # ── AppSync Data Sources (Lambda) ─────────────────────────────

        request_follow_ds = self.api.add_lambda_data_source(
            "RequestFollowDS", request_follow_fn
        )
        accept_follow_ds = self.api.add_lambda_data_source(
            "AcceptFollowDS", accept_follow_fn
        )
        get_followers_ds = self.api.add_lambda_data_source(
            "GetFollowersDS", get_followers_fn
        )
        get_followings_ds = self.api.add_lambda_data_source(
            "GetFollowingsDS", get_followings_fn
        )
        get_notifications_ds = self.api.add_lambda_data_source(
            "GetNotificationsDS", get_notifications_fn
        )

        # ── Resolvers: attach data source to schema operations ────────

        request_follow_ds.create_resolver(
            "RequestFollowResolver",
            type_name="Mutation",
            field_name="requestFollow",
        )
        accept_follow_ds.create_resolver(
            "AcceptFollowResolver",
            type_name="Mutation",
            field_name="acceptFollowRequest",
        )
        get_followers_ds.create_resolver(
            "GetFollowersResolver",
            type_name="Query",
            field_name="getMyFollowers",
        )
        get_followings_ds.create_resolver(
            "GetFollowingsResolver",
            type_name="Query",
            field_name="getMyFollowings",
        )
        get_notifications_ds.create_resolver(
            "GetNotificationsResolver",
            type_name="Query",
            field_name="getMyNotifications",
        )

        # ── Outputs ───────────────────────────────────────────────────
        cdk.CfnOutput(self, "GraphQLApiUrl", value=self.api.graphql_url)
        cdk.CfnOutput(self, "GraphQLApiId",  value=self.api.api_id)
        #cdk.CfnOutput(self,"GraphQLApiUrl",value=self.api.graphql_url)

