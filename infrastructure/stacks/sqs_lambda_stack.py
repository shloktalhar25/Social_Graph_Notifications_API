import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_sqs as sqs,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_event_sources,
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
        notification_queue,     # <- queue passed IN, created in AppSyncStack
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.notification_processor_fn = _lambda.Function(
            self, "NotificationProcessorFn",
            function_name="social-notification-processor",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                "functions/notification_processor",
                bundling=cdk.BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_10.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -r . /asset-output"
                    ],
                ),
            ),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "NOTIFICATION_TABLE_NAME": notification_table.table_name,
                "LOG_LEVEL": "INFO",
            },
        )