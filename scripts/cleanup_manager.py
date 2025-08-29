#!/usr/bin/env python3
"""Resource cleanup with proper S3 and S3 Vectors API usage."""

import sys
import json
from pathlib import Path
from botocore.exceptions import ClientError

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from aws_config import create_s3_client, create_s3vectors_client, create_cloudformation_client

# Add src to path for state manager
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from backend.deployment_state_manager import DeploymentStateManager
except ImportError:
    class DeploymentStateManager:
        def load_state(self): return {}

class CleanupManager:
    """Surgical cleanup for project-related S3 and S3 Vector buckets only."""
    
    def __init__(self):
        try:
            self.s3_client = create_s3_client()
            self.s3vectors_client = create_s3vectors_client()
            self.cf_client = create_cloudformation_client()
            self.state_manager = DeploymentStateManager()
        except RuntimeError as e:
            print(f"❌ {e}")
            sys.exit(1)
    
    def cleanup(self, args) -> int:
        """Cleanup only project-related S3 resources."""
        print("🧹 Cleaning project S3 resources...")
        
        try:
            # Get project bucket names from CloudFormation
            project_buckets = self._get_project_buckets()
            
            if not project_buckets:
                print("ℹ️  No project buckets found")
                return 0
            
            # Categorize project buckets by type
            all_s3_buckets = self._get_all_s3_buckets()
            all_vector_buckets = self._get_all_vector_buckets()
            
            # Clean only project-related buckets
            cleaned_count = 0
            for bucket_name in project_buckets:
                if bucket_name in all_vector_buckets:
                    print(f"🎯 Project S3 Vector bucket: {bucket_name}")
                    self._empty_vector_bucket(bucket_name)
                    cleaned_count += 1
                elif bucket_name in all_s3_buckets:
                    print(f"🎯 Project S3 bucket: {bucket_name}")
                    self._empty_s3_bucket(bucket_name)
                    cleaned_count += 1
                else:
                    print(f"⚠️  Project bucket not found: {bucket_name}")
            
            print(f"✅ Cleaned {cleaned_count} project buckets")
            return 0
        except Exception as e:
            print(f"❌ Cleanup failed: {e}")
            return 1
    
    def _get_project_buckets(self) -> list:
        """Get project bucket names from CloudFormation outputs."""
        try:
            # Get stack name from deployment state
            state = self.state_manager.load_state()
            stack_name = state.get('stack_name', 'bedrock-chatbot')
            
            # Get CloudFormation outputs
            response = self.cf_client.describe_stacks(StackName=stack_name)
            outputs = response['Stacks'][0].get('Outputs', [])
            
            # Extract bucket names from outputs
            bucket_names = []
            for output in outputs:
                key = output['OutputKey']
                value = output['OutputValue']
                # Look for bucket-related outputs
                if 'bucket' in key.lower() and 'name' in key.lower():
                    bucket_names.append(value)
                    print(f"📋 Found project bucket: {value}")
            
            return bucket_names
            
        except ClientError as e:
            if 'does not exist' in str(e):
                print("⚠️  No CloudFormation stack found")
            else:
                print(f"⚠️  Failed to get CloudFormation outputs: {e}")
            return []
        except Exception as e:
            print(f"⚠️  Error retrieving project buckets: {e}")
            return []
    
    def _get_all_s3_buckets(self) -> set:
        """Get all S3 bucket names."""
        try:
            response = self.s3_client.list_buckets()
            return {b['Name'] for b in response['Buckets']}
        except Exception:
            return set()
    
    def _get_all_vector_buckets(self) -> set:
        """Get all S3 Vector bucket names."""
        try:
            response = self.s3vectors_client.list_vector_buckets()
            return {b['vectorBucketName'] for b in response['vectorBuckets']}
        except Exception:
            return set()
    
    def _empty_s3_bucket(self, bucket_name: str):
        """Empty standard S3 bucket."""
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket_name):
                if 'Contents' in page:
                    objects = [{'Key': obj['Key']} for obj in page['Contents']]
                    if objects:
                        self.s3_client.delete_objects(
                            Bucket=bucket_name,
                            Delete={'Objects': objects}
                        )
            print(f"✅ S3 bucket emptied: {bucket_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchBucket':
                print(f"⚠️  S3 bucket not found: {bucket_name}")
            else:
                print(f"❌ Failed to empty S3 bucket {bucket_name}: {e}")
    
    def _empty_vector_bucket(self, bucket_name: str):
        """Empty S3 Vector bucket."""
        try:
            # List indexes
            response = self.s3vectors_client.list_indexes(vectorBucketName=bucket_name)
            indexes = response.get('indexes', [])
            
            # Delete each index
            for index in indexes:
                index_name = index['indexName']
                print(f"   Deleting index: {index_name}")
                
                # Delete vectors in index
                try:
                    paginator = self.s3vectors_client.get_paginator('list_vectors')
                    for page in paginator.paginate(
                        vectorBucketName=bucket_name,
                        indexName=index_name
                    ):
                        vectors = page.get('vectors', [])
                        if vectors:
                            keys = [v['key'] for v in vectors]
                            self.s3vectors_client.delete_vectors(
                                vectorBucketName=bucket_name,
                                indexName=index_name,
                                keys=keys
                            )
                except Exception as e:
                    print(f"   ⚠️  Error deleting vectors: {e}")
                
                # Delete the index
                try:
                    self.s3vectors_client.delete_index(
                        vectorBucketName=bucket_name,
                        indexName=index_name
                    )
                except Exception as e:
                    print(f"   ⚠️  Error deleting index: {e}")
            
            print(f"✅ S3 Vector bucket emptied: {bucket_name}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NotFoundException':
                print(f"⚠️  S3 Vector bucket not found: {bucket_name}")
            else:
                print(f"❌ Failed to empty S3 Vector bucket {bucket_name}: {e}")
        except Exception as e:
            print(f"❌ Failed to empty S3 Vector bucket {bucket_name}: {e}")
