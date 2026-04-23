import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
)
from constructs import Construct


class DynamoDBStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Users Table
        # PK: USER#<userId>   SK: PROFILE
        self.user_table = dynamodb.Table(
            self, "UserTable",
            table_name="social-users",
            partition_key=dynamodb.Attribute(
                name="PK",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # free tier friendly
            removal_policy=RemovalPolicy.DESTROY,  # easy cleanup during dev
        )

        # Follow Table
        # PK: USER#<userId>   SK: FOLLOWS#<targetId>
        # GSI PK: USER#<targetId>  SK: FOLLOWER#<userId>
        self.follow_table = dynamodb.Table(
            self, "FollowTable",
            table_name="social-follows",
            partition_key=dynamodb.Attribute(
                name="PK",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )

        # GSI to query followers direction (who follows a given user)
        self.follow_table.add_global_secondary_index(
            index_name="GSI-FollowerIndex",
            partition_key=dynamodb.Attribute(
                name="GSI_PK",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="GSI_SK",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Notification Table
        # PK: USER#<userId>   SK: NOTIF#<timestamp>#<uuid>
        self.notification_table = dynamodb.Table(
            self, "NotificationTable",
            table_name="social-notifications",
            partition_key=dynamodb.Attribute(
                name="PK",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Output table names for reference
        cdk.CfnOutput(self, "UserTableName", value=self.user_table.table_name)
        cdk.CfnOutput(self, "FollowTableName", value=self.follow_table.table_name)
        cdk.CfnOutput(self, "NotificationTableName", value=self.notification_table.table_name)