import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_cognito as cognito,
    aws_lambda as _lambda,
    aws_iam as iam,
    Duration,
)
from constructs import Construct


class CognitoStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        user_table,          # DynamoDB Table passed in from DynamoDBStack
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Post Confirmation Lambda ──────────────────────────────────
        # Fires after a user confirms signup → saves profile to DynamoDB
        self.post_confirmation_fn = _lambda.Function(
            self, "PostConfirmationFn",
            function_name="social-post-confirmation",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("functions/post_confirmation"),
            timeout=Duration.seconds(10),
            environment={
                "USER_TABLE_NAME": user_table.table_name,
            },
        )

        # Grant Lambda permission to write to the Users table
        user_table.grant_write_data(self.post_confirmation_fn)

        # ── Cognito User Pool ─────────────────────────────────────────
        self.user_pool = cognito.UserPool(
            self, "SocialUserPool",
            user_pool_name="social-graph-user-pool",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=True,
            ),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                fullname=cognito.StandardAttribute(required=False, mutable=True),
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_digits=True,
                require_lowercase=True,
                require_uppercase=False,
                require_symbols=False,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            # Attach the post confirmation trigger
            lambda_triggers=cognito.UserPoolTriggers(
                post_confirmation=self.post_confirmation_fn
            ),
        )

        # ── User Pool Client ──────────────────────────────────────────
        # The "app client" — used by AppSync and test scripts to auth
        self.user_pool_client = self.user_pool.add_client(
            "SocialAppClient",
            user_pool_client_name="social-app-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,     # allows username+password login
                user_srp=True,          # secure remote password (recommended)
            ),
            generate_secret=False,      # no secret needed for public clients
        )

        # Outputs
        cdk.CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        cdk.CfnOutput(self, "UserPoolClientId", value=self.user_pool_client.user_pool_client_id)
        