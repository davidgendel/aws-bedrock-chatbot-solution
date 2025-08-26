#!/usr/bin/env python3
"""
Script to clean up old vectors and document metadata from S3.
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import boto3

# Add the src/backend directory to the path so we can import our modules
backend_path = str(Path(__file__).parent.parent / "src" / "backend")
sys.path.insert(0, backend_path)

from s3_vector_utils import cleanup_old_vectors, list_vector_indexes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Clean up old vectors and document metadata")
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Delete vectors older than this many days (default: 90)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us-east-1",
        help="AWS region (default: us-east-1)"
    )
    return parser.parse_args()


def setup_environment(region: str):
    """Set up environment variables for S3 Vector operations."""
    # Load configuration
    config_path = Path(__file__).parent.parent / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
        
        # Get AWS account ID for bucket naming
        # Use signed client for enhanced security
        try:
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).parent.parent / "lambda_function"))
            from aws_client_factory import AWSClientFactory
            sts_client = AWSClientFactory.create_client("sts", region_name=region, enable_signing=True)
        except ImportError:
            # Fallback to regular boto3 client
            sts_client = boto3.client("sts", region_name=region)
        account_id = sts_client.get_caller_identity()["Account"]
        
        # Set environment variables
        os.environ["AWS_REGION"] = region
        os.environ["VECTOR_INDEX_NAME"] = config.get("s3Vectors", {}).get("indexName", "chatbot-document-vectors")
        os.environ["VECTOR_BUCKET_NAME"] = f"chatbot-vectors-{account_id}-{region}"
        os.environ["METADATA_BUCKET_NAME"] = f"chatbot-metadata-{account_id}-{region}"
    else:
        logger.warning("Config file not found, using default values")
        os.environ["AWS_REGION"] = region
        os.environ["VECTOR_INDEX_NAME"] = "chatbot-document-vectors"


def cleanup_vectors(days_old: int, dry_run: bool = False) -> Dict[str, Any]:
    """
    Clean up old vectors and metadata.
    
    Args:
        days_old: Delete vectors older than this many days
        dry_run: If True, show what would be deleted without deleting
        
    Returns:
        Cleanup statistics
    """
    try:
        logger.info(f"Starting vector cleanup (older than {days_old} days)")
        
        if dry_run:
            logger.info("DRY RUN MODE - No actual deletions will be performed")
        
        # List available vector indexes
        indexes = list_vector_indexes()
        logger.info(f"Found {len(indexes)} vector indexes")
        
        if not indexes:
            logger.warning("No vector indexes found")
            return {"vectors_deleted": 0, "documents_processed": 0}
        
        # Perform cleanup
        if not dry_run:
            cleanup_result = cleanup_old_vectors(days_old)
        else:
            # For dry run, we'll simulate the cleanup
            cleanup_result = {"vectors_deleted": 0, "documents_processed": 0}
            logger.info("Dry run completed - no actual cleanup performed")
        
        return cleanup_result
        
    except Exception as e:
        logger.error(f"Error during vector cleanup: {e}")
        raise


def cleanup_metadata(days_old: int, dry_run: bool = False) -> Dict[str, Any]:
    """
    Clean up old document metadata.
    
    Args:
        days_old: Delete metadata older than this many days
        dry_run: If True, show what would be deleted without deleting
        
    Returns:
        Cleanup statistics
    """
    try:
        metadata_bucket = os.environ.get("METADATA_BUCKET_NAME")
        if not metadata_bucket:
            logger.warning("METADATA_BUCKET_NAME not set, skipping metadata cleanup")
            return {"metadata_deleted": 0}
        
        try:
            s3_client = AWSClientFactory.create_client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"), enable_signing=True)
        except:
            s3_client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # List metadata objects
        response = s3_client.list_objects_v2(
            Bucket=metadata_bucket,
            Prefix="documents/"
        )
        
        if "Contents" not in response:
            logger.info("No metadata objects found")
            return {"metadata_deleted": 0}
        
        objects_to_delete = []
        
        for obj in response["Contents"]:
            if obj["LastModified"].replace(tzinfo=None) < cutoff_date:
                objects_to_delete.append({"Key": obj["Key"]})
        
        logger.info(f"Found {len(objects_to_delete)} metadata objects to delete")
        
        if objects_to_delete and not dry_run:
            # Delete in batches
            deleted_count = 0
            batch_size = 1000
            
            for i in range(0, len(objects_to_delete), batch_size):
                batch = objects_to_delete[i:i + batch_size]
                s3_client.delete_objects(
                    Bucket=metadata_bucket,
                    Delete={"Objects": batch}
                )
                deleted_count += len(batch)
            
            logger.info(f"Deleted {deleted_count} metadata objects")
            return {"metadata_deleted": deleted_count}
        else:
            return {"metadata_deleted": len(objects_to_delete) if dry_run else 0}
        
    except Exception as e:
        logger.error(f"Error during metadata cleanup: {e}")
        return {"metadata_deleted": 0}


def main():
    """Main function."""
    args = parse_args()
    
    try:
        # Setup environment
        setup_environment(args.region)
        
        logger.info("Starting S3 Vector cleanup process")
        logger.info(f"Region: {args.region}")
        logger.info(f"Days old threshold: {args.days}")
        logger.info(f"Dry run: {args.dry_run}")
        
        # Clean up vectors
        vector_result = cleanup_vectors(args.days, args.dry_run)
        
        # Clean up metadata
        metadata_result = cleanup_metadata(args.days, args.dry_run)
        
        # Combine results
        total_result = {
            **vector_result,
            **metadata_result
        }
        
        # Print summary
        logger.info("Cleanup completed successfully")
        logger.info(f"Vectors deleted: {total_result.get('vectors_deleted', 0)}")
        logger.info(f"Documents processed: {total_result.get('documents_processed', 0)}")
        logger.info(f"Metadata deleted: {total_result.get('metadata_deleted', 0)}")
        
        # Print results as JSON for programmatic use
        print(json.dumps(total_result, indent=2))
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
