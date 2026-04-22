import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_sqs as sqs,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_event_sources,
    aws_iam as iam,
    Duration,
)
from constructs import Construct


class SqsLambdaStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        notification_table,     
        follow_table,           
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Dead Letter Queue ─────────────────────────────────────────
        # If notification processing fails 3x, message goes here
        dlq = sqs.Queue(
            self, "NotificationDLQ",
            queue_name="social-notifications-dlq",
            retention_period=Duration.days(14),
        )

        # ── Main Notification Queue ───────────────────────────────────
        self.notification_queue = sqs.Queue(
            self, "NotificationQueue",
            queue_name=f"{construct_id}-notifications-queue",  # 
            visibility_timeout=Duration.seconds(60),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,    # retry 3x before DLQ
                queue=dlq,
            ),
        )

        # ── Notification Processor Lambda ─────────────────────────────
        # Consumes SQS → writes notifications to DynamoDB
        
        self.notification_processor_fn = _lambda.Function(
            self, "NotificationProcessorFn",
            function_name="social-notification-processor",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("functions/notification_processor"),
            timeout=Duration.seconds(30),
            memory_size = 256,
            environment={
                "NOTIFICATION_TABLE_NAME": notification_table.table_name,
                # APPSYNC_API_URL will be added later
                "LOG_LEVEL": "INFO",
            },
        )


        # Allow Lambda to read from SQS
        self.notification_queue.grant_consume_messages(self.notification_processor_fn)

        # Allow Lambda to write to DynamoDB directly (our chosen approach)
        notification_table.grant_write_data(self.notification_processor_fn)
        follow_table.grant_read_data(self.notification_processor_fn)

        # Wire SQS as event source for the Lambda
        self.notification_processor_fn.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.notification_queue,
                batch_size=10,          # process up to 10 messages at once
                report_batch_item_failures=True,  # partial batch success
            )
        )

        # Output queue URL so AppSync resolvers can publish to it
        cdk.CfnOutput(self, "NotificationQueueUrl", value=self.notification_queue.queue_url)