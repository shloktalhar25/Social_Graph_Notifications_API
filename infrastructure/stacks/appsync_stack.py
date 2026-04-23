import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_appsync as appsync,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_sqs as sqs,
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
        search_fn,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── SQS Queue lives here — same stack as resolvers that publish to it
        dlq = sqs.Queue(
            self, "NotificationDLQ",
            queue_name="social-notif-dlq",
            retention_period=Duration.days(14),
        )
        self.notification_queue = sqs.Queue(
            self, "NotificationQueue",
            queue_name="social-notifi-queue",
            visibility_timeout=Duration.seconds(60),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=dlq,
            ),
        )

        shared_env = {
            "USER_TABLE_NAME":         user_table.table_name,
            "FOLLOW_TABLE_NAME":       follow_table.table_name,
            "NOTIFICATION_TABLE_NAME": notification_table.table_name,
            "NOTIFICATION_QUEUE_URL":  self.notification_queue.queue_url,
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
        self.request_follow_fn = _lambda.Function(
            self, "RequestFollowFn",
            function_name="social-request-follow",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("functions/resolvers/request_follow"),
            timeout=Duration.seconds(15),
            environment=shared_env,
        )

        self.accept_follow_fn = _lambda.Function(
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

        create_notification_fn = _lambda.Function(
            self, "CreateNotificationFn",
            function_name="social-create-notification",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("functions/resolvers/create_notification"),
            timeout=Duration.seconds(10),
            environment=shared_env,
        )

        # ── IAM Grants ────────────────────────────────────────────────
        user_table.grant_read_data(self.request_follow_fn)
        follow_table.grant_read_write_data(self.request_follow_fn)
        self.notification_queue.grant_send_messages(self.request_follow_fn)

        user_table.grant_read_data(self.accept_follow_fn)
        follow_table.grant_read_write_data(self.accept_follow_fn)
        self.notification_queue.grant_send_messages(self.accept_follow_fn)

        follow_table.grant_read_data(get_followers_fn)
        follow_table.grant_read_data(get_followings_fn)
        notification_table.grant_read_data(get_notifications_fn)
        notification_table.grant_write_data(create_notification_fn)

        # ── AppSync Data Sources ──────────────────────────────────────
        request_follow_ds      = self.api.add_lambda_data_source("RequestFollowDS",      self.request_follow_fn)
        accept_follow_ds       = self.api.add_lambda_data_source("AcceptFollowDS",       self.accept_follow_fn)
        get_followers_ds       = self.api.add_lambda_data_source("GetFollowersDS",       get_followers_fn)
        get_followings_ds      = self.api.add_lambda_data_source("GetFollowingsDS",      get_followings_fn)
        get_notifications_ds   = self.api.add_lambda_data_source("GetNotificationsDS",   get_notifications_fn)
        create_notification_ds = self.api.add_lambda_data_source("CreateNotificationDS", create_notification_fn)
        search_ds              = self.api.add_lambda_data_source("SearchResolverDS",     search_fn)

        # ── Resolvers ─────────────────────────────────────────────────
        request_follow_ds.create_resolver(
            "RequestFollowResolver",
            type_name="Mutation", field_name="requestFollow",
        )
        accept_follow_ds.create_resolver(
            "AcceptFollowResolver",
            type_name="Mutation", field_name="acceptFollowRequest",
        )
        get_followers_ds.create_resolver(
            "GetFollowersResolver",
            type_name="Query", field_name="getMyFollowers",
        )
        get_followings_ds.create_resolver(
            "GetFollowingsResolver",
            type_name="Query", field_name="getMyFollowings",
        )
        get_notifications_ds.create_resolver(
            "GetNotificationsResolver",
            type_name="Query", field_name="getMyNotifications",
        )
        create_notification_ds.create_resolver(
            "CreateNotificationResolver",
            type_name="Mutation", field_name="createNotification",
        )
        search_ds.create_resolver(
            "SearchFollowersResolver",
            type_name="Query", field_name="searchMyFollowers",
        )
        search_ds.create_resolver(
            "SearchFollowingsResolver",
            type_name="Query", field_name="searchMyFollowings",
        )

        self.api_id = self.api.api_id

        cdk.CfnOutput(self, "GraphQLApiUrl", value=self.api.graphql_url)
        cdk.CfnOutput(self, "GraphQLApiId",  value=self.api.api_id)
        cdk.CfnOutput(self, "NotificationQueueUrl", value=self.notification_queue.queue_url)