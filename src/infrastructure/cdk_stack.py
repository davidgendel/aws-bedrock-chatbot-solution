"""
CDK stack for the chatbot RAG solution - Fixed and properly structured.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

import aws_cdk as cdk
import aws_cdk.aws_apigateway as apigateway
import aws_cdk.aws_apigatewayv2 as apigwv2
import aws_cdk.aws_apigatewayv2_integrations as apigwv2_integrations
import aws_cdk.aws_cloudfront as cloudfront
import aws_cdk.aws_cloudfront_origins as origins
import aws_cdk.aws_cloudwatch as cloudwatch
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_events as events
import aws_cdk.aws_events_targets as targets
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_logs as logs
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_s3_notifications as s3n
import aws_cdk.aws_wafv2 as wafv2
from constructs import Construct


class ChatbotRagStack(cdk.Stack):
    """CDK stack for the chatbot RAG solution."""

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        """Initialize the stack."""
        super().__init__(scope, id, **kwargs)

        # Load configuration
        config_path = Path(__file__).parent.parent.parent / "config.json"
        with open(config_path, "r") as f:
            self.config = json.load(f)

        # Create all infrastructure components in proper order
        self.s3_buckets = self._create_s3_buckets()
        self.guardrail = self._create_bedrock_guardrail()
        self.lambda_role = self._create_lambda_role()
        self.vector_indexes = self._create_vector_indexes()
        self._complete_lambda_role_permissions()  # Complete permissions after vector indexes exist
        self.log_groups = self._create_log_groups()
        self.lambda_functions = self._create_lambda_functions()
        self.api_gateway = self._create_api_gateway()
        self.websocket_api = self._create_websocket_api()
        self.cloudfront = self._create_cloudfront_distribution()
        self.waf = self._create_waf()
        self.monitoring = self._create_monitoring()
        self._create_outputs()

    def _create_vector_indexes(self) -> Dict[str, Any]:
        """Create S3 Vector buckets and indexes using the S3 Vectors service."""
        s3_vectors_config = self.config.get("s3Vectors", {})
        
        # S3 Vector bucket name
        vector_bucket_name = f"chatbot-vectors-{self.account}-{self.region}"
        
        # Vector index configuration
        vector_config = {
            "bucket_name": vector_bucket_name,
            "index_name": s3_vectors_config.get("indexName", "chatbot-document-vectors"),
            "dimensions": s3_vectors_config.get("dimensions", 1536),  # Amazon Titan embeddings
            "similarity_metric": s3_vectors_config.get("similarityMetric", "COSINE"),
            "index_type": "HNSW",  # Hierarchical Navigable Small World
            "ef_construction": 200,  # Build-time parameter
            "m": 16,  # Number of bi-directional links
        }
        
        # Create metadata bucket for document information (regular S3)
        metadata_bucket = s3.Bucket(
            self, "MetadataBucket", 
            bucket_name=f"chatbot-metadata-{self.account}-{self.region}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        
        # Create a Lambda layer with the latest boto3 version
        boto3_layer = lambda_.LayerVersion(
            self, "LatestBoto3Layer",
            code=lambda_.Code.from_asset("layers/boto3-layer"),  # We'll create this directory
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[lambda_.Architecture.ARM_64],
            description="Latest boto3 1.39.17+ with S3 Vectors support"
        )

        # Custom resource to create S3 Vector bucket and index using correct S3 Vectors service API
        vector_setup_creator = lambda_.Function(
            self, "VectorSetupCreator",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,  # Use ARM architecture for better performance
            handler="index.handler",
            timeout=cdk.Duration.minutes(5),
            memory_size=256,  # Increased memory for better performance
            role=self.lambda_role,
            layers=[boto3_layer],  # Use the latest boto3 layer
            environment={
                "PYTHONPATH": "/opt/python:/var/runtime",
            },
            code=lambda_.Code.from_inline(f"""
# Ensure we're using the latest boto3 version with S3 Vectors support
import sys
import os

# Add the layer path to Python path for latest boto3
layer_path = '/opt/python'
if layer_path not in sys.path:
    sys.path.insert(0, layer_path)

import boto3
import json
import logging
import urllib3

# Log boto3 version for debugging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def send_response(event, context, response_status, response_data=None, physical_resource_id=None, reason=None):
    \"\"\"Send response to CloudFormation.\"\"\"
    if response_data is None:
        response_data = {{}}
    
    response_url = event['ResponseURL']
    response_body = {{
        'Status': response_status,
        'Reason': reason or f'See CloudWatch Log Stream: {{context.log_stream_name}}',
        'PhysicalResourceId': physical_resource_id or context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': response_data
    }}
    
    json_response_body = json.dumps(response_body)
    headers = {{'content-type': '', 'content-length': str(len(json_response_body))}}
    
    try:
        http = urllib3.PoolManager()
        response = http.request('PUT', response_url, body=json_response_body, headers=headers)
        logger.info(f"CloudFormation response sent: {{response.status}}")
    except Exception as e:
        logger.error(f"Failed to send CloudFormation response: {{e}}")

def handler(event, context):
    try:
        logger.info(f"Using boto3 version: {{boto3.__version__}}")
        logger.info(f"Event: {{json.dumps(event)}}")
        
        request_type = event['RequestType']
        bucket_name = '{vector_bucket_name}'
        index_name = '{vector_config["index_name"]}'
        vector_dimensions = {vector_config["dimensions"]}
        similarity_metric = '{vector_config["similarity_metric"].lower()}'
        physical_resource_id = f'{{bucket_name}}-{{index_name}}'
        
        if request_type == 'Create':
            # Create S3 Vector bucket and index using CORRECT S3 Vectors service API
            try:
                s3vectors_client = boto3.client('s3vectors', region_name='{self.region}')
                logger.info("Successfully created s3vectors client")
                logger.info(f"Available services: {{boto3.Session().get_available_services()}}")
            except Exception as client_error:
                logger.error(f"Failed to create s3vectors client: {{client_error}}")
                send_response(event, context, 'FAILED', reason=f"S3 Vectors service not available: {{client_error}}")
                return
            
            # First create the vector bucket using CORRECT camelCase API
            try:
                bucket_response = s3vectors_client.create_vector_bucket(
                    vectorBucketName=bucket_name  # camelCase parameter
                )
                logger.info(f"Created S3 Vector bucket: {{bucket_response}}")
            except Exception as bucket_error:
                if 'VectorBucketAlreadyExists' in str(bucket_error) or 'BucketAlreadyExists' in str(bucket_error):
                    logger.info(f"S3 Vector bucket {{bucket_name}} already exists")
                else:
                    logger.error(f"Failed to create vector bucket: {{bucket_error}}")
                    send_response(event, context, 'FAILED', reason=f"Failed to create vector bucket: {{bucket_error}}")
                    return
            
            # Then create the index using CORRECT camelCase API with separate parameters
            try:
                index_response = s3vectors_client.create_index(
                    vectorBucketName=bucket_name,        # camelCase parameter
                    indexName=index_name,                # camelCase parameter
                    dataType='float32',                  # lowercase value
                    dimension=vector_dimensions,         # integer value
                    distanceMetric=similarity_metric     # evaluated string
                )
                logger.info(f"Created S3 Vector index: {{index_response}}")
            except Exception as index_error:
                if 'IndexAlreadyExists' in str(index_error) or 'ResourceAlreadyExists' in str(index_error):
                    logger.info(f"S3 Vector index {{index_name}} already exists")
                else:
                    logger.error(f"Failed to create vector index: {{index_error}}")
                    send_response(event, context, 'FAILED', reason=f"Failed to create vector index: {{index_error}}")
                    return
            
            # Success response
            send_response(event, context, 'SUCCESS', 
                         response_data={{'VectorBucketName': bucket_name, 'IndexName': index_name}},
                         physical_resource_id=physical_resource_id)
            
        elif request_type == 'Delete':
            # Delete S3 Vector index and bucket using CORRECT camelCase API methods
            try:
                s3vectors_client = boto3.client('s3vectors', region_name='{self.region}')
            except Exception as client_error:
                logger.warning(f"S3 Vectors client not available during deletion: {{client_error}}")
                # Don't fail deletion if service is not available
                send_response(event, context, 'SUCCESS', 
                             response_data={{'VectorBucketName': bucket_name, 'IndexName': index_name}},
                             physical_resource_id=physical_resource_id)
                return
                
            try:
                # First delete the index using camelCase parameters
                s3vectors_client.delete_index(
                    vectorBucketName=bucket_name,  # camelCase parameter
                    indexName=index_name           # camelCase parameter
                )
                logger.info(f"Deleted S3 Vector index: {{index_name}}")
                
                # Then delete the bucket using camelCase parameter
                s3vectors_client.delete_vector_bucket(
                    vectorBucketName=bucket_name   # camelCase parameter
                )
                logger.info(f"Deleted S3 Vector bucket: {{bucket_name}}")
            except Exception as e:
                logger.warning(f"Failed to delete vector resources: {{e}}")
                # Don't fail deletion if resources are already gone
            
            # Success response for deletion
            send_response(event, context, 'SUCCESS', 
                         response_data={{'VectorBucketName': bucket_name, 'IndexName': index_name}},
                         physical_resource_id=physical_resource_id)
        
        elif request_type == 'Update':
            # For updates, just return success (no changes needed)
            send_response(event, context, 'SUCCESS', 
                         response_data={{'VectorBucketName': bucket_name, 'IndexName': index_name}},
                         physical_resource_id=physical_resource_id)
        
    except Exception as e:
        logger.error(f"Unexpected error: {{e}}")
        import traceback
        logger.error(f"Traceback: {{traceback.format_exc()}}")
        send_response(event, context, 'FAILED', reason=f"Unexpected error: {{e}}")
        return
            """)
        )
        
        # Custom resource to trigger vector setup
        vector_setup_resource = cdk.CustomResource(
            self, "VectorSetupResource",
            service_token=vector_setup_creator.function_arn,
            properties={
                "VectorBucketName": vector_bucket_name,
                "IndexName": vector_config["index_name"]
            }
        )
        
        # Create a proxy object for the S3 Vector bucket that other methods can reference
        # This is needed because S3 Vectors buckets are created via API calls, not CDK constructs
        class VectorBucketProxy:
            def __init__(self, bucket_name: str, account: str, region: str):
                self.bucket_name = bucket_name
                self.bucket_arn = f"arn:aws:s3vectors:{region}:{account}:bucket/{bucket_name}"
        
        vector_bucket_proxy = VectorBucketProxy(vector_bucket_name, self.account, self.region)
        
        return {
            "config": vector_config,
            "metadata_bucket": metadata_bucket,
            "vector_setup_resource": vector_setup_resource,
            "vector_bucket": vector_bucket_proxy  # Add the missing vector_bucket reference
        }

    def _complete_lambda_role_permissions(self) -> None:
        """Complete Lambda role permissions after vector indexes are created."""
        # Add permissions for metadata bucket now that it exists
        self.lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject", 
                    "s3:PutObject", 
                    "s3:DeleteObject",
                    "s3:ListBucket"
                ],
                resources=[
                    self.vector_indexes["metadata_bucket"].bucket_arn,
                    f"{self.vector_indexes['metadata_bucket'].bucket_arn}/*"
                ],
            )
        )

    def _create_s3_buckets(self) -> Dict[str, s3.Bucket]:
        """Create S3 buckets for documents and website assets."""
        document_bucket = s3.Bucket(
            self, "DocumentBucket",
            bucket_name=f"chatbot-documents-{self.account}-{self.region}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        website_bucket = s3.Bucket(
            self, "WebsiteBucket",
            bucket_name=f"chatbot-website-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        return {
            "document_bucket": document_bucket,
            "website_bucket": website_bucket
        }

    def _create_bedrock_guardrail(self) -> Optional[Any]:
        """Create Bedrock guardrail if configured with fallback options."""
        guardrail_config = self.config.get("bedrock", {}).get("guardrails", {})
        
        if not guardrail_config.get("createDefault", False):
            return None
        
        try:
            # Import bedrock constructs with error handling
            import aws_cdk.aws_bedrock as bedrock
        except ImportError:
            print("Warning: Bedrock constructs not available, skipping guardrail creation")
            return None
        
        try:
            default_config = guardrail_config.get("defaultGuardrailConfig", {})
            
            # Simplified content policy filters with error handling
            content_filters = []
            try:
                for filter_config in default_config.get("contentPolicyConfig", {}).get("filters", []):
                    content_filters.append(bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type=filter_config.get("type", "HATE"),
                        input_strength=filter_config.get("strength", "MEDIUM"),
                        output_strength=filter_config.get("strength", "MEDIUM")
                    ))
            except Exception as e:
                print(f"Warning: Error creating content filters, using defaults: {e}")
                # Fallback to basic content filter
                content_filters = [
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type="HATE",
                        input_strength="MEDIUM",
                        output_strength="MEDIUM"
                    )
                ]
            
            # Simplified word policy with error handling
            word_filters = []
            try:
                for word_list in default_config.get("wordPolicyConfig", {}).get("managedWordLists", []):
                    word_filters.append(bedrock.CfnGuardrail.ManagedWordsConfigProperty(
                        type=word_list.get("type", "PROFANITY")
                    ))
            except Exception as e:
                print(f"Warning: Error creating word filters, using defaults: {e}")
                # Fallback to basic profanity filter
                word_filters = [
                    bedrock.CfnGuardrail.ManagedWordsConfigProperty(type="PROFANITY")
                ]
            
            # Simplified PII entities with error handling - removed for cost efficiency
            pii_entities = []
            
            # Create the guardrail with error handling
            guardrail = bedrock.CfnGuardrail(
                self, "ChatbotGuardrail",
                name=default_config.get("name", "ChatbotDefaultGuardrail"),
                description=default_config.get("description", "Default guardrail for chatbot"),
                blocked_input_messaging="I can't process that request due to content policy restrictions.",
                blocked_outputs_messaging="I can't provide that information due to content policy restrictions.",
                content_policy_config=bedrock.CfnGuardrail.ContentPolicyConfigProperty(
                    filters_config=content_filters
                ) if content_filters else None,
                word_policy_config=bedrock.CfnGuardrail.WordPolicyConfigProperty(
                    managed_word_lists_config=word_filters
                ) if word_filters else None
                # Removed sensitive information policy for cost efficiency
                # Removed complex topic policy to avoid deployment issues
            )
            
            # Create a version of the guardrail with error handling
            try:
                guardrail_version = bedrock.CfnGuardrailVersion(
                    self, "ChatbotGuardrailVersion",
                    guardrail_identifier=guardrail.attr_guardrail_id,
                    description="Version 1 of the chatbot guardrail"
                )
            except Exception as e:
                print(f"Warning: Error creating guardrail version: {e}")
                guardrail_version = None
            
            return {
                "guardrail": guardrail,
                "version": guardrail_version
            }
            
        except Exception as e:
            print(f"Warning: Error creating Bedrock guardrail, proceeding without: {e}")
            return None

    def _create_lambda_role(self) -> iam.Role:
        """Create Lambda execution role with necessary permissions."""
        lambda_role = iam.Role(
            self, "ChatbotLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )

        # Add permissions for Bedrock
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:ApplyGuardrail",
                ],
                resources=["*"],
            )
        )

        # Add permissions for S3 Vectors service (will be refined after vector indexes are created)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3vectors:CreateVectorBucket",
                    "s3vectors:DeleteVectorBucket",
                    "s3vectors:GetVectorBucket",
                    "s3vectors:ListVectorBuckets",
                    "s3vectors:CreateIndex",
                    "s3vectors:DeleteIndex", 
                    "s3vectors:GetIndex",
                    "s3vectors:ListIndexes",
                    "s3vectors:PutVectors",
                    "s3vectors:QueryVectors",
                    "s3vectors:DeleteVectors",
                    "s3vectors:ListVectors",
                    "s3vectors:GetVectors"
                ],
                resources=["*"]  # S3 Vectors permissions are typically granted on all resources
            )
        )

        # Add permissions for regular S3 buckets (documents) - metadata bucket will be added later
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject", 
                    "s3:PutObject", 
                    "s3:DeleteObject",
                    "s3:ListBucket"
                ],
                resources=[
                    self.s3_buckets["document_bucket"].bucket_arn,
                    f"{self.s3_buckets['document_bucket'].bucket_arn}/*"
                ],
            )
        )

        # Add permissions for Textract
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["textract:AnalyzeDocument"],
                resources=["*"],
            )
        )

        return lambda_role

    def _create_log_groups(self) -> Dict[str, logs.LogGroup]:
        """Create CloudWatch log groups with different retention periods."""
        return {
            "critical_logs": logs.LogGroup(
                self, "CriticalLogs",
                log_group_name="/aws/lambda/ChatbotRagStack-Critical",
                retention=logs.RetentionDays.ONE_WEEK,
                removal_policy=cdk.RemovalPolicy.DESTROY,
            ),
            "standard_logs": logs.LogGroup(
                self, "StandardLogs",
                log_group_name="/aws/lambda/ChatbotRagStack-Standard",
                retention=logs.RetentionDays.THREE_DAYS,
                removal_policy=cdk.RemovalPolicy.DESTROY,
            ),
            "debug_logs": logs.LogGroup(
                self, "DebugLogs",
                log_group_name="/aws/lambda/ChatbotRagStack-Debug",
                retention=logs.RetentionDays.ONE_DAY,
                removal_policy=cdk.RemovalPolicy.DESTROY,
            )
        }

    def _create_lambda_layers(self) -> Dict[str, lambda_.LayerVersion]:
        """Create Lambda layers for heavy dependencies."""
        # Create dependencies layer
        dependencies_layer = lambda_.LayerVersion(
            self, "ChatbotDependenciesLayer",
            code=lambda_.Code.from_asset(
                str(Path(__file__).parent.parent.parent / "lambda_layer"),
                bundling=cdk.BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output/python/ && "
                        "find /asset-output -name '*.pyc' -delete && "
                        "find /asset-output -name '__pycache__' -type d -exec rm -rf {} + || true"
                    ],
                    user="root",
                )
            ),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[lambda_.Architecture.ARM_64],
            description="Heavy dependencies layer for chatbot (NumPy, etc.)",
        )
        
        return {
            "dependencies": dependencies_layer
        }

    def _create_lambda_functions(self) -> Dict[str, Any]:
        """Create Lambda functions for chatbot and document processing."""
        # Create Lambda layers first
        layers = self._create_lambda_layers()
        
        # Create main chatbot Lambda function with layers
        chatbot_function = lambda_.Function(
            self, "ChatbotFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="lambda_handler.handler",
            code=lambda_.Code.from_asset(str(Path(__file__).parent.parent.parent / "lambda_function")),
            layers=[layers["dependencies"]],
            timeout=cdk.Duration.seconds(30),
            memory_size=512,  # Increased for better performance with layers
            role=self.lambda_role,
            environment={
                "VECTOR_INDEX_NAME": self.vector_indexes["config"]["index_name"],
                "VECTOR_BUCKET_NAME": self.vector_indexes["config"]["bucket_name"],
                "METADATA_BUCKET_NAME": self.vector_indexes["metadata_bucket"].bucket_name,
                "DOCUMENT_BUCKET_NAME": self.s3_buckets["document_bucket"].bucket_name,
                "BEDROCK_MODEL_ID": self.config["bedrock"]["modelId"],
                "REGION": self.region,
                "CRITICAL_LOG_GROUP": self.log_groups["critical_logs"].log_group_name,
                "STANDARD_LOG_GROUP": self.log_groups["standard_logs"].log_group_name,
                "DEBUG_LOG_GROUP": self.log_groups["debug_logs"].log_group_name,
                "GUARDRAIL_ID": self.guardrail["guardrail"].attr_guardrail_id if self.guardrail and self.guardrail.get("guardrail") else "",
                "GUARDRAIL_VERSION": self.guardrail["version"].attr_version if self.guardrail and self.guardrail.get("version") else ""
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Create Lambda alias for provisioned concurrency
        chatbot_alias = lambda_.Alias(
            self, "ChatbotFunctionAlias",
            alias_name="live",
            version=chatbot_function.current_version,
        )

        # Configure provisioned concurrency if enabled
        if self.config.get("lambda", {}).get("chatbot", {}).get("provisionedConcurrency", {}).get("enabled"):
            concurrent_executions = self.config["lambda"]["chatbot"]["provisionedConcurrency"]["concurrentExecutions"]
            
            # Note: Provisioned concurrency temporarily disabled for CDK compatibility
            # TODO: Re-enable when CDK version supports CfnProvisionedConcurrencyConfig
            pass

        # Document processing is now handled locally, not via Lambda
        # This reduces Lambda package size and allows full use of heavy dependencies

        return {
            "chatbot_function": chatbot_function,
            "chatbot_alias": chatbot_alias,
        }

    def _create_api_gateway(self) -> Dict[str, Any]:
        """Create API Gateway for REST endpoints."""
        api = apigateway.RestApi(
            self, "ChatbotApi",
            rest_api_name="Chatbot RAG API",
            description="API for the RAG chatbot solution",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key"],
            ),
            # Add binary media types for file uploads
            binary_media_types=["multipart/form-data", "application/octet-stream"],
        )

        # Create API key and usage plan
        api_key = api.add_api_key("ChatbotApiKey", api_key_name="ChatbotApiKey")
        usage_plan = api.add_usage_plan(
            "ChatbotUsagePlan",
            name="ChatbotUsagePlan",
            throttle=apigateway.ThrottleSettings(
                rate_limit=self.config["api"]["throttling"]["ratePerMinute"],
                burst_limit=self.config["api"]["throttling"]["ratePerHour"],
            ),
        )
        usage_plan.add_api_key(api_key)
        usage_plan.add_api_stage(stage=api.deployment_stage)

        # Function to use for endpoints
        function_to_use = (
            self.lambda_functions["chatbot_alias"] 
            if self.config.get("lambda", {}).get("chatbot", {}).get("provisionedConcurrency", {}).get("enabled")
            else self.lambda_functions["chatbot_function"]
        )

        # Add chat endpoint
        chat_resource = api.root.add_resource("chat")
        chat_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(function_to_use),
            api_key_required=True,
        )

        # Add health endpoint (no API key required for monitoring)
        health_resource = api.root.add_resource("health")
        health_resource.add_method(
            "GET",
            apigateway.MockIntegration(
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": '{"status": "healthy", "timestamp": "$context.requestTime"}'
                        }
                    )
                ],
                request_templates={
                    "application/json": '{"statusCode": 200}'
                }
            ),
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_models={
                        "application/json": apigateway.Model.EMPTY_MODEL
                    }
                )
            ]
        )

        return {
            "api": api,
            "api_key": api_key
        }

    def _create_websocket_api(self) -> apigwv2.WebSocketApi:
        """Create WebSocket API for streaming responses."""
        function_to_use = (
            self.lambda_functions["chatbot_alias"] 
            if self.config.get("lambda", {}).get("chatbot", {}).get("provisionedConcurrency", {}).get("enabled")
            else self.lambda_functions["chatbot_function"]
        )

        websocket_api = apigwv2.WebSocketApi(
            self, "ChatbotWebSocketApi",
            connect_route_options=apigwv2.WebSocketRouteOptions(
                integration=apigwv2_integrations.WebSocketLambdaIntegration(
                    "ConnectIntegration", function_to_use
                )
            ),
            disconnect_route_options=apigwv2.WebSocketRouteOptions(
                integration=apigwv2_integrations.WebSocketLambdaIntegration(
                    "DisconnectIntegration", function_to_use
                )
            ),
        )

        # Add routes
        websocket_api.add_route(
            "sendMessage",
            integration=apigwv2_integrations.WebSocketLambdaIntegration(
                "SendMessageIntegration", function_to_use
            )
        )

        # Deploy the WebSocket API
        websocket_stage = apigwv2.WebSocketStage(
            self, "ChatbotWebSocketStage",
            web_socket_api=websocket_api,
            stage_name="prod",
            auto_deploy=True,
        )

        # Grant permissions for WebSocket management
        function_to_use.add_to_role_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections"],
                resources=[
                    f"arn:aws:execute-api:{self.region}:{self.account}:{websocket_api.api_id}/{websocket_stage.stage_name}/POST/@connections/*"
                ]
            )
        )

        # Update Lambda environment with WebSocket API URL
        chatbot_function = self.lambda_functions["chatbot_function"]
        chatbot_function.add_environment("WEBSOCKET_API_URL", websocket_stage.url)

        return websocket_api

    def _create_cloudfront_distribution(self) -> cloudfront.Distribution:
        """Create CloudFront distribution for website assets."""
        # Create Origin Access Identity for S3 bucket access
        origin_access_identity = cloudfront.OriginAccessIdentity(
            self, "ChatbotOAI",
            comment="OAI for Chatbot website bucket"
        )

        # Grant CloudFront access to the S3 bucket
        self.s3_buckets["website_bucket"].grant_read(origin_access_identity)

        return cloudfront.Distribution(
            self, "ChatbotDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    self.s3_buckets["website_bucket"],
                    origin_access_identity=origin_access_identity
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD,
                compress=True,
            ),
            additional_behaviors={
                # Cache JavaScript files longer
                "*.js": cloudfront.BehaviorOptions(
                    origin=origins.S3Origin(
                        self.s3_buckets["website_bucket"],
                        origin_access_identity=origin_access_identity
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                    compress=True,
                ),
                # Cache HTML files with shorter TTL
                "*.html": cloudfront.BehaviorOptions(
                    origin=origins.S3Origin(
                        self.s3_buckets["website_bucket"],
                        origin_access_identity=origin_access_identity
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,  # Don't cache HTML for updates
                    compress=True,
                ),
            },
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.minutes(5)
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.minutes(5)
                )
            ],
            # Geo restrictions - allow only US and Canada
            geo_restriction=cloudfront.GeoRestriction.allowlist("US", "CA"),
            # Price class 100 - Use only North America and Europe edge locations
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            comment="CloudFront distribution for Chatbot widget - US/CA only",
            enabled=True,
            http_version=cloudfront.HttpVersion.HTTP2,
        )

    def _create_waf(self) -> wafv2.CfnWebACL:
        """Create WAF Web ACL for API protection."""
        web_acl = wafv2.CfnWebACL(
            self, "ChatbotWebAcl",
            scope="REGIONAL",
            default_action={"allow": {}},
            rules=[
                {
                    "name": "AWSManagedRulesCommonRuleSet",
                    "priority": 1,
                    "overrideAction": {"none": {}},
                    "statement": {
                        "managedRuleGroupStatement": {
                            "vendorName": "AWS",
                            "name": "AWSManagedRulesCommonRuleSet",
                        }
                    },
                    "visibilityConfig": {
                        "sampledRequestsEnabled": True,
                        "cloudWatchMetricsEnabled": True,
                        "metricName": "CommonRuleSetMetric",
                    },
                },
                {
                    "name": "RateLimitRule",
                    "priority": 2,
                    "action": {"block": {}},
                    "statement": {
                        "rateBasedStatement": {
                            "limit": 100,
                            "aggregateKeyType": "IP",
                        }
                    },
                    "visibilityConfig": {
                        "sampledRequestsEnabled": True,
                        "cloudWatchMetricsEnabled": True,
                        "metricName": "RateLimitMetric",
                    },
                },
            ],
            visibility_config={
                "sampledRequestsEnabled": True,
                "cloudWatchMetricsEnabled": True,
                "metricName": "ChatbotWebAcl",
            },
        )

        # Associate WAF with API Gateway
        wafv2.CfnWebACLAssociation(
            self, "ChatbotWebAclAssociation",
            resource_arn=self.api_gateway["api"].deployment_stage.stage_arn,
            web_acl_arn=web_acl.attr_arn,
        )

        return web_acl

    def _create_monitoring(self) -> cloudwatch.Dashboard:
        """Create CloudWatch dashboard for monitoring."""
        return cloudwatch.Dashboard(
            self, "ChatbotDashboard",
            dashboard_name="ChatbotMonitoring",
            widgets=[
                [
                    cloudwatch.GraphWidget(
                        title="API Requests",
                        left=[self.api_gateway["api"].metric_count()],
                        width=8,
                    ),
                    cloudwatch.GraphWidget(
                        title="Lambda Invocations",
                        left=[self.lambda_functions["chatbot_function"].metric_invocations()],
                        width=8,
                    ),
                    cloudwatch.GraphWidget(
                        title="S3 Vector Operations",
                        left=[
                            cloudwatch.Metric(
                                namespace="AWS/S3",
                                metric_name="NumberOfObjects",
                                dimensions_map={
                                    "BucketName": self.vector_indexes["vector_bucket"].bucket_name,
                                },
                            ),
                        ],
                        width=8,
                    ),
                ],
            ],
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        cdk.CfnOutput(
            self, "CloudFrontDomain",
            value=self.cloudfront.distribution_domain_name,
            description="CloudFront distribution domain name",
        )

        cdk.CfnOutput(
            self, "DocumentBucketName",
            value=self.s3_buckets["document_bucket"].bucket_name,
            description="S3 bucket name for documents",
        )

        cdk.CfnOutput(
            self, "WebsiteBucketName",
            value=self.s3_buckets["website_bucket"].bucket_name,
            description="S3 bucket name for website assets",
        )

        cdk.CfnOutput(
            self, "WebSocketApiUrl",
            value=f"wss://{self.websocket_api.api_id}.execute-api.{self.region}.amazonaws.com/prod",
            description="WebSocket API URL for streaming responses",
        )

        cdk.CfnOutput(
            self, "VectorIndexName",
            value=self.vector_indexes["config"]["index_name"],
            description="S3 Vector index name for document embeddings",
        )

        cdk.CfnOutput(
            self, "VectorBucketName",
            value=self.vector_indexes["config"]["bucket_name"],
            description="S3 Vector bucket name for vector storage",
        )

        cdk.CfnOutput(
            self, "MetadataBucketName",
            value=self.vector_indexes["metadata_bucket"].bucket_name,
            description="S3 bucket name for document metadata",
        )

        cdk.CfnOutput(
            self, "ApiEndpoint",
            value=self.api_gateway["api"].url,
            description="REST API Gateway endpoint URL",
        )

        cdk.CfnOutput(
            self, "ApiKey",
            value=self.api_gateway["api_key"].key_arn,
            description="API Gateway API Key ARN",
        )

        cdk.CfnOutput(
            self, "WebSocketEndpoint",
            value=f"wss://{self.websocket_api.api_id}.execute-api.{self.region}.amazonaws.com/prod",
            description="WebSocket API endpoint URL",
        )

        cdk.CfnOutput(
            self, "CloudFrontUrl",
            value=f"https://{self.cloudfront.distribution_domain_name}",
            description="CloudFront distribution URL",
        )
