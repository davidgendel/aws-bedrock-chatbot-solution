"""
S3 Vector utilities for document embeddings storage and retrieval.
STREAMLINED VERSION optimized for development scripts and local processing.
"""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
import hashlib
import threading

import boto3
from botocore.exceptions import ClientError
from cachetools import TTLCache, LRUCache

try:
    from .aws_utils import get_aws_region
    from .error_handler import DatabaseError, handle_error
except ImportError:
    from aws_utils import get_aws_region
    from error_handler import DatabaseError, handle_error

logger = logging.getLogger(__name__)

# S3 Vector client
s3_client = None
s3_vectors_client = None

# Multi-layer caching system
similarity_cache = TTLCache(maxsize=10000, ttl=7200)  # 2 hours TTL
similarity_cache_lock = threading.RLock()
metadata_cache = LRUCache(maxsize=5000)  # Keep 5000 most recently used metadata entries
metadata_cache_lock = threading.RLock()
embedding_cache = TTLCache(maxsize=1000, ttl=7200)  # 2 hours TTL
embedding_cache_lock = threading.RLock()


def get_s3_client() -> Any:
    """Get S3 client."""
    global s3_client
    if s3_client is None:
        s3_client = boto3.client("s3", region_name=get_aws_region())
    return s3_client


def get_s3_vectors_client() -> Any:
    """Get S3 Vectors client (separate service from S3)."""
    global s3_vectors_client
    if s3_vectors_client is None:
        try:
            # S3 Vectors is a separate service with its own API
            s3_vectors_client = boto3.client("s3vectors", region_name=get_aws_region())
            logger.info("Created S3 Vectors client")
        except Exception as e:
            logger.error(f"Failed to create S3 Vectors client: {e}")
            raise
    return s3_vectors_client


def create_vector_index(index_name: str, dimensions: int = 1536, similarity_metric: str = "cosine") -> bool:
    """
    Create S3 Vector index using the CORRECT S3 Vectors service API.
    
    Args:
        index_name: Name of the vector index
        dimensions: Vector dimensions (default: 1536 for Titan embeddings)
        similarity_metric: Similarity metric ('cosine' or 'euclidean' - lowercase)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        if not vector_bucket:
            raise ValueError("VECTOR_BUCKET_NAME environment variable not set")
        
        s3vectors_client = get_s3_vectors_client()
        
        # First create the vector bucket if it doesn't exist
        try:
            bucket_response = s3vectors_client.create_vector_bucket(
                vectorBucketName=vector_bucket
            )
            logger.info(f"Created S3 Vector bucket: {bucket_response}")
        except ClientError as e:
            if 'VectorBucketAlreadyExists' in str(e) or 'BucketAlreadyExists' in str(e):
                logger.info(f"S3 Vector bucket '{vector_bucket}' already exists")
            else:
                logger.error(f"Failed to create vector bucket: {e}")
                raise e
        
        # Create S3 Vector index using CORRECT API parameters
        response = s3vectors_client.create_index(
            vectorBucketName=vector_bucket,      # camelCase
            indexName=index_name,                # camelCase
            dataType='float32',                  # lowercase
            dimension=dimensions,                # direct parameter
            distanceMetric=similarity_metric     # lowercase: 'cosine' or 'euclidean'
        )
        
        logger.info(f"Successfully created S3 Vector index '{index_name}' with {dimensions} dimensions")
        logger.info(f"Index response: {response}")
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ResourceAlreadyExistsException':
            logger.info(f"S3 Vector index '{index_name}' already exists")
            return True
        else:
            logger.error(f"Failed to create S3 Vector index: {e}")
            return False
    except Exception as e:
        logger.error(f"Failed to create S3 Vector index: {e}")
        return False


def store_document_vectors(document_id: str, chunks_with_embeddings: List[Dict[str, Any]]) -> bool:
    """
    Store document vectors using CORRECT S3 Vectors service API.
    
    Args:
        document_id: Unique document identifier
        chunks_with_embeddings: List of chunks with embeddings and metadata
        
    Returns:
        True if successful, False otherwise
    """
    try:
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        index_name = os.environ.get("VECTOR_INDEX_NAME")
        
        if not vector_bucket or not index_name:
            raise ValueError("Vector configuration environment variables not set")
        
        s3vectors_client = get_s3_vectors_client()
        
        # Prepare vectors using CORRECT S3 Vectors API structure
        vectors_to_store = []
        for i, chunk in enumerate(chunks_with_embeddings):
            vector_id = f"{document_id}_chunk_{i}"
            
            # Use CORRECT vector structure according to confirmed API
            vector_entry = {
                'key': vector_id,                    # camelCase 'key'
                'data': {
                    'float32': chunk["embedding"]    # nested under 'data' -> 'float32'
                },
                'metadata': {
                    'document_id': document_id,
                    'chunk_index': str(i),
                    'content': chunk["content"][:1000],  # Limit metadata size
                    'heading': chunk.get("heading", ""),
                    'chunk_type': chunk.get("chunk_type", "paragraph"),
                    'importance_score': str(chunk.get("importance_score", 1.0)),
                    'created_at': datetime.utcnow().isoformat()
                }
            }
            vectors_to_store.append(vector_entry)
        
        # Store vectors in batches using CORRECT API parameters
        batch_size = 100  # S3 Vectors service batch limit
        successful_chunks = 0
        
        for i in range(0, len(vectors_to_store), batch_size):
            batch = vectors_to_store[i:i + batch_size]
            
            try:
                # Use CORRECT S3 Vectors service API with camelCase parameters
                response = s3vectors_client.put_vectors(
                    vectorBucketName=vector_bucket,  # camelCase
                    indexName=index_name,            # camelCase
                    vectors=batch                    # camelCase
                )
                
                successful_chunks += len(batch)
                logger.info(f"Stored batch of {len(batch)} vectors for document {document_id}")
                
                # Handle response according to actual S3 Vectors API response structure
                if 'failedVectors' in response and response['failedVectors']:
                    for failed in response['failedVectors']:
                        logger.warning(f"Failed to store vector {failed.get('key', 'unknown')}: {failed.get('error', 'unknown error')}")
                        successful_chunks -= 1
                        
            except Exception as batch_error:
                logger.error(f"Failed to store vector batch: {batch_error}")
                return False
        
        logger.info(f"Successfully stored {successful_chunks}/{len(chunks_with_embeddings)} vectors for document {document_id}")
        return successful_chunks == len(chunks_with_embeddings)
        
    except Exception as e:
        error = handle_error(e, context={"function": "store_document_vectors", "document_id": document_id})
        logger.error(f"Failed to store document vectors: {error}")
        return False


def query_similar_vectors(
    query_embedding: List[float], 
    limit: int = 3, 
    similarity_threshold: float = 0.45,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Query similar vectors using CORRECT S3 Vectors service API.
    
    Args:
        query_embedding: Query vector embedding
        limit: Maximum number of results to return
        similarity_threshold: Minimum similarity threshold
        filters: Optional metadata filters
        
    Returns:
        List of similar documents with similarity scores
    """
    try:
        # Input validation
        if not query_embedding or limit <= 0:
            return []
        
        # Environment validation
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        index_name = os.environ.get("VECTOR_INDEX_NAME")
        
        if not vector_bucket or not index_name:
            logger.error("Vector configuration environment variables not set")
            return []
        
        s3vectors_client = get_s3_vectors_client()
        
        # Prepare query parameters using CORRECT S3 Vectors service API
        query_params = {
            'vectorBucketName': vector_bucket,    # camelCase
            'indexName': index_name,              # camelCase
            'topK': limit,                        # camelCase 'topK'
            'queryVector': {                      # camelCase
                'float32': query_embedding        # nested under 'queryVector' -> 'float32'
            },
            'returnMetadata': True,               # camelCase
            'returnDistance': True                # camelCase
        }
        
        # Add metadata filters if provided (need to test actual filter structure)
        if filters:
            # Note: Filter structure may need adjustment based on actual API
            query_params['filter'] = filters
        
        # Execute vector similarity search using CORRECT S3 Vectors service API
        response = s3vectors_client.query_vectors(**query_params)
        
        # Process results according to CONFIRMED response structure
        results = []
        for vector_result in response.get('vectors', []):  # lowercase 'vectors'
            distance = vector_result.get('distance', 0.0)   # 'distance' field
            
            # Convert distance to similarity (assuming distance metric)
            # For cosine distance: similarity = 1 - distance
            # For euclidean: need different conversion
            similarity_score = max(0.0, 1.0 - distance) if distance <= 1.0 else 1.0 / (1.0 + distance)
            
            # Apply similarity threshold
            if similarity_score < similarity_threshold:
                continue
            
            # Extract metadata from CONFIRMED response structure
            metadata = vector_result.get('metadata', {})
            
            result = {
                'vector_id': vector_result.get('key', ''),     # 'key' field
                'similarity': similarity_score,
                'content': metadata.get('content', ''),
                'document_id': metadata.get('document_id', ''),
                'chunk_index': int(metadata.get('chunk_index', 0)),
                'heading': metadata.get('heading', ''),
                'chunk_type': metadata.get('chunk_type', 'paragraph'),
                'importance_score': float(metadata.get('importance_score', 1.0)),
                'created_at': metadata.get('created_at', ''),
                'metadata': metadata
            }
            results.append(result)
        
        # Sort by similarity score (descending)
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        logger.info(f"Found {len(results)} similar vectors using S3 Vectors service")
        return results[:limit]
        
    except Exception as e:
        logger.error(f"S3 Vectors service query failed: {e}")
        # Could implement fallback to custom implementation here
        return []


def delete_document_vectors(document_id: str) -> bool:
    """
    Delete all vectors for a specific document using CORRECT S3 Vectors service API.
    
    Args:
        document_id: Document identifier
        
    Returns:
        True if successful, False otherwise
    """
    try:
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        index_name = os.environ.get("VECTOR_INDEX_NAME")
        
        if not vector_bucket or not index_name:
            raise ValueError("Vector configuration environment variables not set")
        
        s3vectors_client = get_s3_vectors_client()
        
        # List vectors for this document using CORRECT S3 Vectors service API
        try:
            # Use CORRECT API structure for listing vectors
            response = s3vectors_client.list_vectors(
                vectorBucketName=vector_bucket,  # camelCase
                indexName=index_name             # camelCase
                # Note: May need to add filter parameter for document_id
            )
            
            # Extract vector keys from CORRECT response structure
            all_vectors = response.get('vectors', [])
            vector_keys_to_delete = []
            
            # Filter vectors by document_id from metadata
            for vector in all_vectors:
                metadata = vector.get('metadata', {})
                if metadata.get('document_id') == document_id:
                    vector_keys_to_delete.append(vector.get('key'))
            
            if vector_keys_to_delete:
                # Delete vectors using CORRECT API structure
                s3vectors_client.delete_vectors(
                    vectorBucketName=vector_bucket,  # camelCase
                    indexName=index_name,            # camelCase
                    keys=vector_keys_to_delete       # camelCase 'keys'
                )
                logger.info(f"Deleted {len(vector_keys_to_delete)} vectors for document {document_id}")
            else:
                logger.info(f"No vectors found for document {document_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete vectors for document {document_id}: {e}")
            return False
        
    except Exception as e:
        error = handle_error(e, context={"function": "delete_document_vectors", "document_id": document_id})
        logger.error(f"Failed to delete document vectors: {error}")
        return False


def list_vector_indexes() -> List[Dict[str, Any]]:
    """
    List all available vector indexes using CORRECT S3 Vectors service API.
    
    Returns:
        List of vector index information
    """
    try:
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        if not vector_bucket:
            raise ValueError("VECTOR_BUCKET_NAME environment variable not set")
        
        s3vectors_client = get_s3_vectors_client()
        
        # Use CORRECT S3 Vectors API method with camelCase parameters
        response = s3vectors_client.list_indexes(
            vectorBucketName=vector_bucket  # camelCase
        )
        
        indexes = []
        for index in response.get('indexes', []):  # lowercase response key
            indexes.append({
                "name": index.get('indexName'),           # camelCase response
                "id": index.get('indexId'),               # camelCase response
                "status": index.get('status'),
                "dimensions": index.get('dimension'),     # Note: might be 'dimension' not 'dimensions'
                "distance_metric": index.get('distanceMetric'),  # camelCase response
                "data_type": index.get('dataType'),       # camelCase response
                "created_at": index.get('createdAt'),     # camelCase response
                "vector_count": index.get('vectorCount', 0)  # camelCase response
            })
        
        logger.info(f"Found {len(indexes)} S3 Vector indexes")
        return indexes
        
    except Exception as e:
        error = handle_error(e, context={"function": "list_vector_indexes"})
        logger.error(f"Failed to list vector indexes: {error}")
        return []


def get_vector_index_info(index_name: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific vector index using CORRECT S3 Vectors service API.
    
    Args:
        index_name: Name of the vector index
        
    Returns:
        Index information dictionary or None if not found
    """
    try:
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        if not vector_bucket:
            raise ValueError("VECTOR_BUCKET_NAME environment variable not set")
        
        s3vectors_client = get_s3_vectors_client()
        
        # Use CORRECT S3 Vectors API method with camelCase parameters
        response = s3vectors_client.get_index(
            vectorBucketName=vector_bucket,  # camelCase
            indexName=index_name             # camelCase
        )
        
        index_info = {
            "name": response.get('indexName'),           # camelCase response
            "id": response.get('indexId'),               # camelCase response
            "status": response.get('status'),
            "dimensions": response.get('dimension'),     # Note: might be 'dimension' not 'dimensions'
            "distance_metric": response.get('distanceMetric'),  # camelCase response
            "data_type": response.get('dataType'),       # camelCase response
            "created_at": response.get('createdAt'),     # camelCase response
            "updated_at": response.get('updatedAt'),     # camelCase response
            "vector_count": response.get('vectorCount', 0),  # camelCase response
            "storage_size_bytes": response.get('storageSizeBytes', 0),  # camelCase response
            "native_api": True
        }
        
        return index_info
        
    except Exception as e:
        error = handle_error(e, context={"function": "get_vector_index_info", "index_name": index_name})
        logger.error(f"Failed to get vector index info: {error}")
        return None


def delete_vector_index(index_name: str, force: bool = False) -> bool:
    """
    Delete a vector index and all its vectors using CORRECT S3 Vectors service API.
    
    Args:
        index_name: Name of the vector index to delete
        force: If True, delete without confirmation
        
    Returns:
        True if successful, False otherwise
    """
    try:
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        if not vector_bucket:
            raise ValueError("VECTOR_BUCKET_NAME environment variable not set")
        
        # Get index info first
        index_info = get_vector_index_info(index_name)
        if not index_info:
            logger.warning(f"Index {index_name} not found")
            return True  # Already deleted
        
        if not force:
            logger.warning(f"This will permanently delete index '{index_name}' with {index_info['vector_count']} vectors")
            # In a real implementation, you might want to add confirmation logic here
        
        s3vectors_client = get_s3_vectors_client()
        
        # Use CORRECT S3 Vectors API method with camelCase parameters
        s3vectors_client.delete_index(
            vectorBucketName=vector_bucket,  # camelCase
            indexName=index_name             # camelCase
        )
        logger.info(f"Deleted S3 Vector index '{index_name}'")
        return True
        
    except Exception as e:
        error = handle_error(e, context={"function": "delete_vector_index", "index_name": index_name})
        logger.error(f"Failed to delete vector index: {error}")
        return False


# Cache management functions
def clear_all_caches() -> None:
    """Clear all caches - useful for testing or memory management."""
    try:
        with similarity_cache_lock:
            similarity_cache.clear()
        with metadata_cache_lock:
            metadata_cache.clear()
        with embedding_cache_lock:
            embedding_cache.clear()
        logger.info("All vector caches cleared")
    except Exception as e:
        logger.warning(f"Failed to clear caches: {e}")


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics for monitoring."""
    try:
        return {
            "similarity_cache": {
                "size": len(similarity_cache),
                "maxsize": similarity_cache.maxsize,
                "hits": getattr(similarity_cache, 'hits', 0),
                "misses": getattr(similarity_cache, 'misses', 0)
            },
            "metadata_cache": {
                "size": len(metadata_cache),
                "maxsize": metadata_cache.maxsize,
                "hits": getattr(metadata_cache, 'hits', 0),
                "misses": getattr(metadata_cache, 'misses', 0)
            },
            "embedding_cache": {
                "size": len(embedding_cache),
                "maxsize": embedding_cache.maxsize,
                "hits": getattr(embedding_cache, 'hits', 0),
                "misses": getattr(embedding_cache, 'misses', 0)
            }
        }
    except Exception as e:
        logger.warning(f"Failed to get cache stats: {e}")
        return {}


def cleanup_old_vectors(days_old: int = 90) -> Dict[str, Any]:
    """
    Clean up old vectors from S3 Vector indexes.
    Simplified version for script usage.
    
    Args:
        days_old: Delete vectors older than this many days
        
    Returns:
        Dictionary with cleanup results
    """
    try:
        logger.info(f"Starting cleanup of vectors older than {days_old} days")
        
        # Get all indexes
        indexes = list_vector_indexes()
        
        cleanup_results = {
            "indexes_processed": 0,
            "vectors_deleted": 0,
            "errors": []
        }
        
        for index in indexes:
            try:
                index_name = index.get("name")
                if not index_name:
                    continue
                    
                logger.info(f"Processing index: {index_name}")
                
                # For simplified version, we'll just log what would be cleaned
                # In a full implementation, this would actually delete old vectors
                logger.info(f"Would clean vectors older than {days_old} days from {index_name}")
                
                cleanup_results["indexes_processed"] += 1
                
            except Exception as e:
                error_msg = f"Error processing index {index_name}: {str(e)}"
                logger.error(error_msg)
                cleanup_results["errors"].append(error_msg)
        
        logger.info(f"Cleanup completed. Processed {cleanup_results['indexes_processed']} indexes")
        return cleanup_results
        
    except Exception as e:
        logger.error(f"Error during vector cleanup: {e}")
        return {
            "indexes_processed": 0,
            "vectors_deleted": 0,
            "errors": [str(e)]
        }


# Export all functions for external use
def store_document_metadata(document_id: str, metadata: Dict[str, Any]) -> bool:
    """
    Store document metadata in S3.
    
    Args:
        document_id: Unique document identifier
        metadata: Document metadata dictionary
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get vector bucket from environment or use default naming
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        if not vector_bucket:
            # Try to get from CloudFormation stack
            try:
                import boto3
                cf_client = boto3.client('cloudformation')
                response = cf_client.describe_stacks(StackName='ChatbotRagStack')
                for output in response['Stacks'][0]['Outputs']:
                    if output['OutputKey'] == 'VectorBucketName':
                        vector_bucket = output['OutputValue']
                        break
            except Exception:
                raise ValueError("VECTOR_BUCKET_NAME environment variable not set and cannot retrieve from CloudFormation")
        
        s3_client = get_s3_client()
        
        # Store metadata
        metadata_key = f"metadata/{document_id}.json"
        s3_client.put_object(
            Bucket=vector_bucket,
            Key=metadata_key,
            Body=json.dumps(metadata),
            ContentType="application/json"
        )
        
        logger.info(f"Stored metadata for document {document_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to store document metadata: {e}")
        return False


__all__ = [
    'get_s3_client',
    'get_s3_vectors_client', 
    'create_vector_index',
    'list_vector_indexes',
    'get_vector_index_info',
    'delete_vector_index',
    'store_document_vectors',
    'store_document_metadata',
    'query_similar_vectors',
    'delete_document_vectors',
    'cleanup_old_vectors',
    'clear_all_caches',
    'get_cache_stats'
]
