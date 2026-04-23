import aws_cdk as cdk
from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_opensearchservice as opensearch,
    aws_iam as iam,
    aws_ec2 as ec2,
)
from constructs import Construct


class OpenSearchStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Service-Linked Role
        # Required for VPC-placed OpenSearch domains.
        # Will fail if it already exists — that's fine, ignore the error.
        # slr = iam.CfnServiceLinkedRole(
        #     self, "OpenSearchSLR",
        #     aws_service_name="es.amazonaws.com",
        # )

        # OpenSearch Domain
        # 2x t3.small.search nodes across 2 AZs → green cluster health
        # Not publicly accessible — IAM-only access policy
        self.domain = opensearch.Domain(
            self, "SocialSearchDomain",
            domain_name="social-graph-search",
            version=opensearch.EngineVersion.OPENSEARCH_2_11,

            capacity=opensearch.CapacityConfig(
                data_nodes=2,
                data_node_instance_type="t3.small.search",
                multi_az_with_standby_enabled=False,  # standby needs 3 nodes
            ),

            ebs=opensearch.EbsOptions(
                volume_size=10,                        # GB per node, minimum
                volume_type=ec2.EbsDeviceVolumeType.GP3,
            ),

            zone_awareness=opensearch.ZoneAwarenessConfig(
                enabled=True,
                availability_zone_count=2,
            ),

            # Security
            encryption_at_rest=opensearch.EncryptionAtRestOptions(enabled=True),
            node_to_node_encryption=True,
            enforce_https=True,

            # Fine-grained access control disabled — we use IAM resource policy
            # which is simpler and sufficient for Lambda-only access
            access_policies=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    principals=[iam.AnyPrincipal()],
                    actions=["es:ESHttp*"],
                    resources=["*"],  # scoped to this domain via resource policy
                    conditions={
                        "StringEquals": {
                            "aws:PrincipalAccount": self.account
                        }
                    },
                )
            ],

            removal_policy=RemovalPolicy.DESTROY,
        )

        # Expose the endpoint for Lambda env vars
        cdk.CfnOutput(
            self, "OpenSearchEndpoint",
            value=self.domain.domain_endpoint,
        )