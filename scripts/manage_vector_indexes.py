#!/usr/bin/env python3
"""
Vector Index Management CLI

This script provides command-line tools for managing vector indexes in the RAG Chatbot system.
It supports both native S3 Vectors API and the fallback S3 implementation.

Usage:
    python3 -m scripts.manage_vector_indexes list
    python3 -m scripts.manage_vector_indexes info <index_name>
    python3 -m scripts.manage_vector_indexes create <index_name> [--dimensions 1536]
    python3 -m scripts.manage_vector_indexes delete <index_name> [--force]
    python3 -m scripts.manage_vector_indexes optimize <index_name>
    python3 -m scripts.manage_vector_indexes stats
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add the src/backend directory to the Python path
backend_path = str(Path(__file__).parent.parent / "src" / "backend")
sys.path.insert(0, backend_path)

from s3_vector_utils import (
    list_vector_indexes,
    get_vector_index_info,
    create_vector_index,
    delete_vector_index,
    optimize_vector_index,
    get_vector_index_stats,
    clear_all_caches,
    get_cache_stats
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VectorIndexManager:
    """Vector index management operations."""
    
    def __init__(self):
        """Initialize the vector index manager."""
        self.setup_environment()
    
    def setup_environment(self):
        """Setup environment variables from config if needed."""
        try:
            # Try to load configuration
            config_path = Path(__file__).parent.parent / "config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                # Set environment variables if not already set
                if not os.environ.get("AWS_REGION"):
                    os.environ["AWS_REGION"] = config.get("region", "us-east-1")
                
                # Set vector bucket name if available in config
                if config.get("vectorBucketName") and not os.environ.get("VECTOR_BUCKET_NAME"):
                    os.environ["VECTOR_BUCKET_NAME"] = config["vectorBucketName"]
                
                # Set vector index name if available in config
                if config.get("vectorIndexName") and not os.environ.get("VECTOR_INDEX_NAME"):
                    os.environ["VECTOR_INDEX_NAME"] = config["vectorIndexName"]
        
        except Exception as e:
            logger.warning(f"Could not load configuration: {e}")
    
    def list_indexes(self) -> None:
        """List all vector indexes."""
        print("📋 Listing Vector Indexes...")
        print("=" * 50)
        
        try:
            indexes = list_vector_indexes()
            
            if not indexes:
                print("No vector indexes found.")
                return
            
            for idx in indexes:
                # Get detailed information for each index
                index_name = idx.get('name')
                if index_name:
                    detailed_info = get_vector_index_info(index_name)
                    if detailed_info:
                        status_emoji = "✅" if detailed_info.get('status') == 'ACTIVE' else "⚠️"
                        api_type = "Native" if detailed_info.get('native_api', False) else "S3"
                        
                        print(f"{status_emoji} {detailed_info['name']}")
                        print(f"   ID: {detailed_info.get('id', 'N/A')}")
                        print(f"   Status: {detailed_info.get('status', 'UNKNOWN')}")
                        print(f"   Dimensions: {detailed_info.get('dimensions', 'N/A')}")
                        print(f"   Similarity: {detailed_info.get('distance_metric', 'N/A')}")
                        print(f"   Data Type: {detailed_info.get('data_type', 'N/A')}")
                        print(f"   Vectors: {detailed_info.get('vector_count', 0):,}")
                        print(f"   API Type: {api_type}")
                        print(f"   Created: {detailed_info.get('created_at', 'N/A')}")
                        print()
                    else:
                        # Fallback to basic info if detailed info fails
                        status_emoji = "⚠️"
                        print(f"{status_emoji} {idx['name']}")
                        print(f"   ID: {idx.get('id', 'N/A')}")
                        print(f"   Status: {idx.get('status', 'UNKNOWN')}")
                        print(f"   Created: {idx.get('created_at', 'N/A')}")
                        print(f"   Note: Could not retrieve detailed information")
                        print()
        
        except Exception as e:
            print(f"❌ Error listing indexes: {e}")
            logger.error(f"Failed to list indexes: {e}")
    
    def show_index_info(self, index_name: str) -> None:
        """Show detailed information about a specific index."""
        print(f"🔍 Index Information: {index_name}")
        print("=" * 50)
        
        try:
            info = get_vector_index_info(index_name)
            
            if not info:
                print(f"❌ Index '{index_name}' not found.")
                return
            
            # Basic information
            status_emoji = "✅" if info.get('status') == 'ACTIVE' else "⚠️"
            api_type = "Native S3 Vectors" if info.get('native_api', False) else "S3 Implementation"
            
            print(f"{status_emoji} Name: {info['name']}")
            print(f"   ID: {info.get('id', 'N/A')}")
            print(f"   Status: {info.get('status', 'UNKNOWN')}")
            print(f"   API Type: {api_type}")
            print()
            
            # Configuration
            print("📊 Configuration:")
            print(f"   Dimensions: {info.get('dimensions', 'N/A')}")
            print(f"   Similarity Metric: {info.get('similarity_metric', 'N/A')}")
            print(f"   Index Type: {info.get('index_type', 'N/A')}")
            print()
            
            # Statistics
            print("📈 Statistics:")
            print(f"   Vector Count: {info.get('vector_count', 0):,}")
            storage_mb = info.get('storage_size_bytes', 0) / (1024 * 1024)
            print(f"   Storage Size: {storage_mb:.2f} MB")
            
            if info.get('partition_count'):
                print(f"   Partitions: {info['partition_count']}")
            print()
            
            # Timestamps
            print("🕒 Timestamps:")
            print(f"   Created: {info.get('created_at', 'N/A')}")
            print(f"   Updated: {info.get('updated_at', 'N/A')}")
            
            # Optimization info
            optimization = info.get('optimization', {})
            if optimization:
                print()
                print("⚡ Optimization:")
                print(f"   Partitioning: {'Enabled' if optimization.get('partitioning_enabled') else 'Disabled'}")
                print(f"   Caching: {'Enabled' if optimization.get('cache_enabled') else 'Disabled'}")
                if optimization.get('last_processed'):
                    print(f"   Last Processed: {optimization['last_optimized']}")
        
        except Exception as e:
            print(f"❌ Error getting index info: {e}")
            logger.error(f"Failed to get index info: {e}")
    
    def create_index(self, index_name: str, dimensions: int = 1536, similarity_metric: str = "COSINE") -> None:
        """Create a new vector index."""
        print(f"🔨 Creating Vector Index: {index_name}")
        print("=" * 50)
        
        try:
            print(f"   Dimensions: {dimensions}")
            print(f"   Similarity Metric: {similarity_metric}")
            print()
            
            if create_vector_index(index_name, dimensions, similarity_metric):
                print(f"✅ Successfully created index '{index_name}'")
            else:
                print(f"❌ Failed to create index '{index_name}'")
        
        except Exception as e:
            print(f"❌ Error creating index: {e}")
            logger.error(f"Failed to create index: {e}")
    
    def delete_index(self, index_name: str, force: bool = False) -> None:
        """Delete a vector index."""
        print(f"🗑️  Deleting Vector Index: {index_name}")
        print("=" * 50)
        
        try:
            # Get index info first
            info = get_vector_index_info(index_name)
            if info:
                print(f"   Vector Count: {info.get('vector_count', 0):,}")
                storage_mb = info.get('storage_size_bytes', 0) / (1024 * 1024)
                print(f"   Storage Size: {storage_mb:.2f} MB")
                print()
            
            if not force:
                confirmation = input("⚠️  This will permanently delete the index and all vectors. Continue? (y/N): ")
                if confirmation.lower() not in ['y', 'yes']:
                    print("❌ Deletion cancelled.")
                    return
            
            if delete_vector_index(index_name, force=True):
                print(f"✅ Successfully deleted index '{index_name}'")
            else:
                print(f"❌ Failed to delete index '{index_name}'")
        
        except Exception as e:
            print(f"❌ Error deleting index: {e}")
            logger.error(f"Failed to delete index: {e}")
    
    def optimize_index(self, index_name: str) -> None:
        """Optimize a vector index."""
        print(f"⚡ Optimizing Vector Index: {index_name}")
        print("=" * 50)
        
        try:
            result = optimize_vector_index(index_name)
            
            if result.get("success"):
                print(f"✅ Successfully processed index '{index_name}'")
                print(f"📊 Vector count: {result.get('vector_count', 'N/A')}")
                print(f"💾 Index size: {result.get('index_size_mb', 'N/A')} MB")
                print(f"🧹 Cache cleared: {result.get('cache_cleared', False)}")
                if result.get("message"):
                    print(f"ℹ️  {result['message']}")
            else:
                print(f"❌ Failed to optimize index '{index_name}'")
                if result.get("error"):
                    print(f"   Error: {result['error']}")
        
        except Exception as e:
            print(f"❌ Error optimizing index: {e}")
            logger.error(f"Failed to optimize index: {e}")
    
    def show_stats(self) -> None:
        """Show comprehensive vector index statistics."""
        print("📊 Vector Index Statistics")
        print("=" * 50)
        
        try:
            stats = get_vector_index_stats()
            
            if not stats.get("success"):
                print(f"❌ Error getting statistics: {stats.get('error', 'Unknown error')}")
                return
            
            # Overall statistics
            print("🌐 Overall Statistics:")
            print(f"   Total Indexes: {stats.get('total_indexes', 0)}")
            
            total_vectors = stats.get('total_vectors', 0)
            if isinstance(total_vectors, (int, float)):
                print(f"   Total Vectors: {total_vectors:,}")
            else:
                print(f"   Total Vectors: {total_vectors}")
            
            total_storage = stats.get('total_storage_mb', 0)
            if isinstance(total_storage, (int, float)):
                print(f"   Total Storage: {total_storage:.2f} MB")
            else:
                print(f"   Total Storage: {total_storage}")
            
            avg_vectors = stats.get('average_vectors_per_index', 0)
            if isinstance(avg_vectors, (int, float)):
                print(f"   Average Vectors/Index: {avg_vectors:.1f}")
            else:
                print(f"   Average Vectors/Index: {avg_vectors}")
            print()
            
            # Cost estimates
            costs = stats.get('estimated_monthly_costs', {})
            if costs:
                print("💰 Estimated Monthly Costs:")
                print(f"   Storage Cost: ${costs.get('total_storage_cost', 0):.4f}")
                print(f"   Query Cost (per 1K): ${costs.get('query_cost_per_1k', 0):.4f}")
                print(f"   Data Processing: ${costs.get('data_processing_cost_per_tb', 0):.4f}/TB")
                print()
            
            # Cache statistics
            cache_stats = stats.get('cache_stats', {})
            if cache_stats:
                print("💾 Cache Statistics:")
                for cache_name, cache_info in cache_stats.items():
                    if isinstance(cache_info, dict):
                        size = cache_info.get('size', 0)
                        maxsize = cache_info.get('maxsize', 0)
                        hits = cache_info.get('hits', 0)
                        misses = cache_info.get('misses', 0)
                        hit_rate = (hits / (hits + misses) * 100) if (hits + misses) > 0 else 0
                        
                        print(f"   {cache_name.replace('_', ' ').title()}:")
                        print(f"     Size: {size}/{maxsize}")
                        print(f"     Hit Rate: {hit_rate:.1f}%")
                print()
            
            # Individual index statistics
            indexes = stats.get('indexes', [])
            if indexes:
                print("📋 Individual Indexes:")
                for idx in indexes:
                    status_emoji = "✅" if idx.get('status') == 'ACTIVE' else "⚠️"
                    
                    print(f"   {status_emoji} {idx['name']}")
                    
                    vector_count = idx.get('vector_count', 0)
                    if isinstance(vector_count, (int, float)):
                        print(f"      Vectors: {vector_count:,}")
                    else:
                        print(f"      Vectors: {vector_count}")
                    
                    storage_mb = idx.get('storage_size_mb', 0)
                    if isinstance(storage_mb, (int, float)):
                        print(f"      Storage: {storage_mb:.2f} MB")
                    else:
                        print(f"      Storage: {storage_mb}")
                    
                    print(f"      Dimensions: {idx.get('dimensions', 0)}")
                    print(f"      Metric: {idx.get('similarity_metric', 'unknown')}")
                    print(f"      Created: {idx.get('created_at', 'unknown')}")
                    print()
            else:
                print("   No indexes found")
        
        except Exception as e:
            print(f"❌ Error getting statistics: {e}")
            logger.error(f"Failed to get statistics: {e}")
    
    def clear_caches(self) -> None:
        """Clear all vector caches."""
        print("🧹 Clearing Vector Caches...")
        print("=" * 50)
        
        try:
            clear_all_caches()
            print("✅ All caches cleared successfully")
        
        except Exception as e:
            print(f"❌ Error clearing caches: {e}")
            logger.error(f"Failed to clear caches: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Vector Index Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 -m scripts.manage_vector_indexes list
  python3 -m scripts.manage_vector_indexes info my-index
  python3 -m scripts.manage_vector_indexes create my-index --dimensions 1536
  python3 -m scripts.manage_vector_indexes delete my-index --force
  python3 -m scripts.manage_vector_indexes optimize my-index
  python3 -m scripts.manage_vector_indexes stats
  python3 -m scripts.manage_vector_indexes clear-cache
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    subparsers.add_parser('list', help='List all vector indexes')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show detailed index information')
    info_parser.add_argument('index_name', help='Name of the index')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new vector index')
    create_parser.add_argument('index_name', help='Name of the index to create')
    create_parser.add_argument('--dimensions', type=int, default=1536, help='Vector dimensions (default: 1536)')
    create_parser.add_argument('--similarity-metric', default='COSINE', choices=['COSINE', 'EUCLIDEAN', 'DOT_PRODUCT'], help='Similarity metric (default: COSINE)')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a vector index')
    delete_parser.add_argument('index_name', help='Name of the index to delete')
    delete_parser.add_argument('--force', action='store_true', help='Delete without confirmation')
    
    # Optimize command
    optimize_parser = subparsers.add_parser('optimize', help='Optimize a vector index')
    optimize_parser.add_argument('index_name', help='Name of the index to optimize')
    
    # Stats command
    subparsers.add_parser('stats', help='Show comprehensive statistics')
    
    # Clear cache command
    subparsers.add_parser('clear-cache', help='Clear all vector caches')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = VectorIndexManager()
    
    try:
        if args.command == 'list':
            manager.list_indexes()
        elif args.command == 'info':
            manager.show_index_info(args.index_name)
        elif args.command == 'create':
            manager.create_index(args.index_name, args.dimensions, args.similarity_metric)
        elif args.command == 'delete':
            manager.delete_index(args.index_name, args.force)
        elif args.command == 'optimize':
            manager.optimize_index(args.index_name)
        elif args.command == 'stats':
            manager.show_stats()
        elif args.command == 'clear-cache':
            manager.clear_caches()
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logger.error(f"Unexpected error in main: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
