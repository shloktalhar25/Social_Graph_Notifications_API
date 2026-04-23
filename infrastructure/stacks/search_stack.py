import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_event_sources,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    Duration,
)
from constructs import Construct


class SearchStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        follow_table,           # DynamoDB follow table (streams enabled)
        opensearch_domain,      # OpenSearch domain from OpenSearchStack
        user_table,             # To enrich follow records with usernames
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        opensearch_endpoint = f"https://{opensearch_domain.domain_endpoint}"

        # ── DynamoDB → OpenSearch Sync Lambda ─────────────────────────
        self.sync_fn = _lambda.Function(
            self, "DynamoToOpenSearchFn",
            function_name="social-dynamo-opensearch-sync",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                "functions/opensearch_sync",
                bundling=cdk.BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_10.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -r . /asset-output"
                    ],
                ),
            ),
            timeout=Duration.seconds(60),
            environment={
                "OPENSEARCH_ENDPOINT": opensearch_endpoint,
                "OPENSEARCH_INDEX":    "social-follows",
                "AWS_ACCOUNT_REGION":  self.region,
            },
        )

        # Allow sync Lambda to read follow and user tables
        follow_table.grant_read_data(self.sync_fn)
        user_table.grant_read_data(self.sync_fn)

        # Allow sync Lambda to write to OpenSearch
        opensearch_domain.grant_index_read_write("*", self.sync_fn)

        # Wire DynamoDB Stream as event source
        self.sync_fn.add_event_source(
            lambda_event_sources.DynamoEventSource(
                follow_table,
                starting_position=_lambda.StartingPosition.TRIM_HORIZON,
                batch_size=100,
                retry_attempts=3,
                report_batch_item_failures=True,
                bisect_batch_on_error=True,
            )
        )

        # ── Search Resolver Lambda ─────────────────────────────────────
        self.search_fn = _lambda.Function(
            self, "SearchResolverFn",
            function_name="social-search-resolver",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                "functions/search_resolver",
                bundling=cdk.BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_10.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -r . /asset-output"
                    ],
                ),
            ),
            timeout=Duration.seconds(15),
            environment={
                "OPENSEARCH_ENDPOINT": opensearch_endpoint,
                "OPENSEARCH_INDEX":    "social-follows",
                "AWS_ACCOUNT_REGION":  self.region,
            },
        )

        # Search resolver only needs read access to OpenSearch
        opensearch_domain.grant_index_read("*", self.search_fn)

        cdk.CfnOutput(self, "SyncFunctionName", value=self.sync_fn.function_name)
        cdk.CfnOutput(self, "SearchFunctionName", value=self.search_fn.function_name)