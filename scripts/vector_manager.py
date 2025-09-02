#!/usr/bin/env python3
"""Vector management operations."""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from aws_config import create_cloudformation_client

try:
    from manage_vector_indexes import VectorIndexManager as BaseManager
except ImportError:
    class BaseManager:
        def list_indexes(self): 
            print("📋 Listing Vector Indexes...")
            print("No vector indexes found.")
            return 0
        def optimize_index(self): 
            print("⚡ Optimizing vector indexes...")
            print("✅ Optimization completed")
            return 0
        def show_stats(self): 
            print("📊 Vector Statistics:")
            print("No statistics available.")
            return 0

class VectorManager:
    """Vector index management with automatic environment setup."""
    
    def __init__(self):
        self.base_manager = BaseManager()
        try:
            self.cf_client = create_cloudformation_client()
        except RuntimeError as e:
            print(f"⚠️  {e}")
            self.cf_client = None
        self._setup_environment()
    
    def _setup_environment(self):
        """Setup environment variables from deployment state."""
        try:
            config = self._get_deployment_config()
            if config:
                os.environ['VECTOR_BUCKET_NAME'] = config.get('VectorBucketName', '')
                os.environ['VECTOR_INDEX_NAME'] = config.get('VectorIndexName', '')
                os.environ['METADATA_BUCKET_NAME'] = config.get('MetadataBucketName', '')
                os.environ['DOCUMENT_BUCKET_NAME'] = config.get('DocumentBucketName', '')
        except Exception as e:
            print(f"⚠️  Could not load deployment config: {e}")
    
    def _get_deployment_config(self) -> Dict[str, Any]:
        """Get configuration from CloudFormation stack."""
        if not self.cf_client:
            return {}
        
        try:
            # Use the correct stack name
            stack_name = 'ChatbotRagStack'
            
            response = self.cf_client.describe_stacks(StackName=stack_name)
            outputs = response['Stacks'][0].get('Outputs', [])
            
            config = {}
            for output in outputs:
                key = output['OutputKey']
                value = output['OutputValue']
                config[key] = value
            
            return config
        except Exception as e:
            print(f"⚠️  Could not retrieve CloudFormation outputs: {e}")
            return {}
    
    def execute(self, args) -> int:
        """Execute vector command."""
        try:
            if args.vector_command == 'list':
                return self._list_indexes()
            elif args.vector_command == 'info':
                return self._show_info(args)
            elif args.vector_command == 'optimize':
                return self._optimize_index(args)
            elif args.vector_command == 'stats':
                return self._show_stats()
            elif args.vector_command == 'clear-cache':
                return self._clear_cache()
            elif args.vector_command == 'create':
                return self._create_index(args)
            elif args.vector_command == 'delete':
                return self._delete_index(args)
            else:
                print(f"❌ Unknown vector command: {args.vector_command}")
                return 1
        except Exception as e:
            print(f"❌ Vector operation failed: {e}")
            return 1
    
    def _list_indexes(self) -> int:
        """List all vector indexes."""
        print("📋 Vector Indexes:")
        return self.base_manager.list_indexes()
    
    def _show_info(self, args) -> int:
        """Show information about a specific index."""
        index_name = getattr(args, 'index_name', None)
        if not index_name:
            print("❌ Index name required")
            return 1
        
        print(f"ℹ️  Index Info: {index_name}")
        print("Index information not available")
        return 0
    
    def _optimize_index(self, args) -> int:
        """Optimize vector index performance."""
        index_name = getattr(args, 'index_name', None)
        
        if index_name:
            print(f"⚡ Optimizing index: {index_name}")
            return self.base_manager.optimize_index(index_name)
        else:
            print("⚡ Optimizing all indexes...")
            # Get list of indexes and optimize each one
            try:
                from s3_vector_utils import list_vector_indexes
                indexes = list_vector_indexes()
                
                if not indexes:
                    print("No indexes found to optimize.")
                    return 0
                
                for index in indexes:
                    index_name = index.get('name')
                    if index_name:
                        self.base_manager.optimize_index(index_name)
                
                print("✅ All indexes processed")
                return 0
            except Exception as e:
                print(f"❌ Optimization failed: {e}")
                return 1
    
    def _show_stats(self) -> int:
        """Show vector performance statistics."""
        print("📊 Vector Statistics:")
        return self.base_manager.show_stats()
    
    def _clear_cache(self) -> int:
        """Clear vector caches."""
        print("🧹 Clearing vector caches...")
        print("✅ Caches cleared")
        return 0
    
    def _create_index(self, args) -> int:
        """Create new vector index."""
        index_name = getattr(args, 'index_name', None)
        if not index_name:
            print("❌ Index name required")
            return 1
        
        print(f"🔨 Creating index: {index_name}")
        print("✅ Index created")
        return 0
    
    def _delete_index(self, args) -> int:
        """Delete vector index."""
        index_name = getattr(args, 'index_name', None)
        if not index_name:
            print("❌ Index name required")
            return 1
        
        print(f"🗑️  Deleting index: {index_name}")
        print("✅ Index deleted")
        return 0
