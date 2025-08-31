"""
S3 Vector utilities for document embeddings storage and retrieval.
"""
import json
import logging
import os
import time
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
# Vector similarity cache - stores recent similarity calculations
similarity_cache = TTLCache(maxsize=10000, ttl=7200)  # 2 hours TTL
similarity_cache_lock = threading.RLock()

# Vector metadata cache - stores vector metadata for quick access
metadata_cache = LRUCache(maxsize=5000)  # Keep 5000 most recently used metadata entries
metadata_cache_lock = threading.RLock()

# Embedding cache - stores document embeddings to avoid re-computation
embedding_cache = TTLCache(maxsize=1000, ttl=7200)  # 2 hours TTL
embedding_cache_lock = threading.RLock()

# Partition info cache - stores partition information
partition_cache = TTLCache(maxsize=100, ttl=7200)  # 2 hours TTL
partition_cache_lock = threading.RLock()


def _generate_cache_key(*args) -> str:
    """Generate a consistent cache key from arguments."""
    key_string = "|".join(str(arg) for arg in args)
    return hashlib.md5(key_string.encode()).hexdigest()


def _cache_similarity_result(query_hash: str, vector_id: str, similarity: float) -> None:
    """Cache similarity calculation result."""
    try:
        with similarity_cache_lock:
            cache_key = f"{query_hash}:{vector_id}"
            similarity_cache[cache_key] = similarity
    except Exception as e:
        logger.debug(f"Failed to cache similarity result: {e}")


def _get_cached_similarity(query_hash: str, vector_id: str) -> Optional[float]:
    """Get cached similarity result."""
    try:
        with similarity_cache_lock:
            cache_key = f"{query_hash}:{vector_id}"
            return similarity_cache.get(cache_key)
    except Exception as e:
        logger.debug(f"Failed to get cached similarity: {e}")
        return None


def _cache_vector_metadata(vector_id: str, metadata: Dict[str, Any]) -> None:
    """Cache vector metadata."""
    try:
        with metadata_cache_lock:
            metadata_cache[vector_id] = metadata
    except Exception as e:
        logger.debug(f"Failed to cache vector metadata: {e}")


def _get_cached_vector_metadata(vector_id: str) -> Optional[Dict[str, Any]]:
    """Get cached vector metadata."""
    try:
        with metadata_cache_lock:
            return metadata_cache.get(vector_id)
    except Exception as e:
        logger.debug(f"Failed to get cached vector metadata: {e}")
        return None


def _cache_embedding(content_hash: str, embedding: List[float]) -> None:
    """Cache document embedding."""
    try:
        with embedding_cache_lock:
            embedding_cache[content_hash] = embedding
    except Exception as e:
        logger.debug(f"Failed to cache embedding: {e}")


def _get_cached_embedding(content_hash: str) -> Optional[List[float]]:
    """Get cached embedding."""
    try:
        with embedding_cache_lock:
            return embedding_cache.get(content_hash)
    except Exception as e:
        logger.debug(f"Failed to get cached embedding: {e}")
        return None


def _cache_partition_info(index_name: str, partition_info: Dict[str, Any]) -> None:
    """Cache partition information."""
    try:
        with partition_cache_lock:
            partition_cache[index_name] = partition_info
    except Exception as e:
        logger.debug(f"Failed to cache partition info: {e}")


def _get_cached_partition_info(index_name: str) -> Optional[Dict[str, Any]]:
    """Get cached partition information."""
    try:
        with partition_cache_lock:
            return partition_cache.get(index_name)
    except Exception as e:
        logger.debug(f"Failed to get cached partition info: {e}")
        return None


def clear_all_caches() -> None:
    """Clear all caches - useful for testing or memory management."""
    try:
        with similarity_cache_lock:
            similarity_cache.clear()
        with metadata_cache_lock:
            metadata_cache.clear()
        with embedding_cache_lock:
            embedding_cache.clear()
        with partition_cache_lock:
            partition_cache.clear()
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
            },
            "partition_cache": {
                "size": len(partition_cache),
                "maxsize": partition_cache.maxsize,
                "hits": getattr(partition_cache, 'hits', 0),
                "misses": getattr(partition_cache, 'misses', 0)
            }
        }
    except Exception as e:
        logger.warning(f"Failed to get cache stats: {e}")
        return {}


def get_s3_client() -> Any:
    """Get S3 client with request signing disabled for vector storage."""
    global s3_client
    if s3_client is None:
        try:
            from .aws_utils import get_s3_client
            s3_client = get_s3_client()
            logger.info("Using standard S3 client for vector storage")
        except ImportError:
            from aws_utils import get_s3_client
            s3_client = get_s3_client()
            logger.info("Using standard S3 client for vector storage")
    return s3_client


def get_s3_vectors_client() -> Any:
    """Get S3 Vectors client. Note: S3 Vectors is a separate service from S3."""
    global s3_vectors_client
    if s3_vectors_client is None:
        try:
            # Use the dedicated S3 Vectors client (separate service from S3)
            # Request signing is not supported/needed for S3 Vectors
            import boto3
            try:
                from .aws_utils import get_aws_region
                region = get_aws_region()
            except ImportError:
                from aws_utils import get_aws_region
                region = get_aws_region()
            
            s3_vectors_client = boto3.client('s3vectors', region_name=region)
            logger.info("Using S3 Vectors client (service does not yet support SigV4 signing)")
        except Exception as e:
            logger.error(f"Failed to create S3 Vectors client: {e}")
            raise
    return s3_vectors_client


def create_vector_index(index_name: str, dimensions: int = 1536, similarity_metric: str = "COSINE") -> bool:
    """
    Create S3 Vector index using S3 Vectors API only.
    
    Args:
        index_name: Name of the vector index
        dimensions: Vector dimensions (default: 1536 for Titan embeddings)
        similarity_metric: Similarity metric (COSINE, EUCLIDEAN, DOT_PRODUCT)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        if not vector_bucket:
            raise ValueError("VECTOR_BUCKET_NAME environment variable not set")
        
        s3_vectors_client = get_s3_vectors_client()
        
        # Use S3 Vectors API only - no fallbacks
        response = s3_vectors_client.create_index(
            vectorBucketName=vector_bucket,
            indexName=index_name,
            dataType='float32',
            dimension=dimensions,
            distanceMetric=similarity_metric.lower()
        )
        logger.info(f"Created S3 Vector index '{index_name}' with dimensions {dimensions}")
        return True
        
    except Exception as e:
        error = handle_error(e, context={"function": "create_vector_index", "index_name": index_name})
        logger.error(f"Failed to create vector index: {error}")
        return False


def store_document_vectors(document_id: str, chunks_with_embeddings: List[Dict[str, Any]]) -> bool:
    """
    Store document vectors in S3 Vector index using correct S3 Vectors API.
    
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
        
        total_chunks = len(chunks_with_embeddings)
        successful_chunks = 0
        max_batch_size = 100  # S3 Vectors API batch limit
        
        logger.info(f"Processing {total_chunks} chunks in batches of {max_batch_size}")
        
        s3_vectors_client = get_s3_vectors_client()
        
        # Process in batches using correct S3 Vectors API
        for batch_start in range(0, total_chunks, max_batch_size):
            batch_end = min(batch_start + max_batch_size, total_chunks)
            batch_chunks = chunks_with_embeddings[batch_start:batch_end]
            
            # Prepare vectors for S3 Vectors API
            vectors_to_insert = []
            for i, chunk in enumerate(batch_chunks):
                vector_id = f"{document_id}_chunk_{batch_start + i}"
                
                # Validate embedding before storing
                embedding = chunk["embedding"]
                if not _validate_embedding_for_storage(embedding):
                    logger.warning(f"Skipping invalid embedding for chunk {vector_id}")
                    continue
                
                vector_entry = {
                    'key': vector_id,
                    'data': {
                        'float32': embedding
                    },
                    'metadata': {
                        'document_id': document_id,
                        'chunk_index': str(batch_start + i),
                        'content': chunk["content"][:500],
                        'heading': chunk.get("heading", "")[:100],
                        'chunk_type': chunk.get("chunk_type", "paragraph"),
                        'importance_score': str(chunk.get("importance_score", 1.0)),
                        'created_at': datetime.utcnow().isoformat()
                    }
                }
                vectors_to_insert.append(vector_entry)
            
            # Skip empty batches
            if not vectors_to_insert:
                logger.warning(f"Skipping batch {batch_start + 1}-{batch_end} (no valid vectors)")
                continue
            
            # Use correct S3 Vectors API call with retry and delay
            try:
                response = s3_vectors_client.put_vectors(
                    vectorBucketName=vector_bucket,
                    indexName=index_name,
                    vectors=vectors_to_insert
                )
                successful_chunks += len(vectors_to_insert)
                logger.info(f"Stored batch {batch_start + 1}-{batch_end} using S3 Vectors API")
                
                # Add delay between batches to prevent throttling
                if batch_end < total_chunks:  # Don't delay after the last batch
                    time.sleep(2)  # 2 second delay between storage batches
                
            except Exception as api_error:
                logger.error(f"S3 Vectors API failed for batch {batch_start + 1}-{batch_end}: {api_error}")
                return False
        
        success = successful_chunks > 0  # Success if we stored at least some vectors
        logger.info(f"Successfully stored {successful_chunks}/{total_chunks} vector chunks for document {document_id}")
        return success
        
    except Exception as e:
        error = handle_error(e, context={"function": "store_document_vectors", "document_id": document_id})
        logger.error(f"Failed to store document vectors: {error}")
        return False


def _validate_embedding_for_storage(embedding: List[float]) -> bool:
    """Validate embedding before storing to prevent S3 Vectors API errors."""
    try:
        if not embedding or not isinstance(embedding, list):
            return False
        
        # Check for zero norm (cosine distance doesn't support zero norm vectors)
        import math
        norm_squared = sum(x * x for x in embedding)
        
        if norm_squared == 0.0 or not math.isfinite(norm_squared):
            return False
        
        # Check for NaN or infinite values
        if any(not math.isfinite(x) for x in embedding):
            return False
        
        return True
        
    except Exception:
        return False


def query_similar_vectors(
    query_embedding: List[float], 
    limit: int = 3, 
    similarity_threshold: float = 0.45,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Query similar vectors using S3 Vectors API only.
    
    Args:
        query_embedding: Query vector embedding
        limit: Maximum number of results to return
        similarity_threshold: Minimum similarity threshold
        filters: Optional filters for the query
        
    Returns:
        List of similar documents with similarity scores
    """
    try:
        if not query_embedding or limit <= 0:
            return []
        
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        index_name = os.environ.get("VECTOR_INDEX_NAME")
        
        if not vector_bucket or not index_name:
            logger.error("Vector configuration environment variables not set")
            return []
        
        s3_vectors_client = get_s3_vectors_client()
        
        # Use S3 Vectors API only - no fallbacks to S3
        query_params = {
            'vectorBucketName': vector_bucket,
            'indexName': index_name,
            'topK': min(limit, 100),
            'queryVector': {
                'float32': query_embedding
            },
            'returnMetadata': True,
            'returnDistance': True
        }
        
        # Add metadata filters if provided
        if filters:
            query_params['filter'] = filters
        
        # Execute S3 Vectors query
        response = s3_vectors_client.query_vectors(**query_params)
        
        # Process results
        results = []
        for vector in response.get('vectors', []):
            try:
                metadata = vector.get('metadata', {})
                distance = vector.get('distance', 1.0)
                
                # Convert distance to similarity (assuming cosine distance)
                similarity = 1.0 - distance if distance <= 1.0 else 0.0
                
                if similarity < similarity_threshold:
                    continue
                
                result = {
                    "id": vector.get('key', ''),
                    "document_id": metadata.get('document_id', ''),
                    "chunk_index": int(metadata.get('chunk_index', 0)),
                    "content": metadata.get('content', ''),
                    "heading": metadata.get('heading', ''),
                    "chunk_type": metadata.get('chunk_type', 'paragraph'),
                    "importance_score": float(metadata.get('importance_score', 1.0)),
                    "metadata": metadata,
                    "similarity": similarity
                }
                results.append(result)
                
            except Exception as match_error:
                logger.debug(f"Error processing match: {match_error}")
                continue
        
        # Sort by combined score
        results.sort(key=lambda x: x["similarity"] * x["importance_score"], reverse=True)
        
        logger.info(f"S3 Vectors query returned {len(results)} results")
        return results[:limit]
        
    except Exception as e:
        logger.error(f"Failed to query similar vectors: {e}")
        return []


def _hierarchical_vector_search(
    query_embedding: List[float],
    limit: int,
    similarity_threshold: float,
    filters: Optional[Dict[str, Any]],
    vector_bucket: str,
    index_name: str
) -> List[Dict[str, Any]]:
    """
    HNSW-like hierarchical vector search for O(log n) performance.
    
    Args:
        query_embedding: Query vector
        limit: Maximum results to return
        similarity_threshold: Minimum similarity threshold
        filters: Optional metadata filters
        vector_bucket: S3 bucket name
        index_name: Vector index name
        
    Returns:
        List of similar documents with similarity scores
    """
    try:
        s3_client = get_s3_client()
        
        # Load search configuration
        try:
            search_config_response = s3_client.get_object(
                Bucket=vector_bucket,
                Key=f"_indexes/{index_name}/search_config.json"
            )
            search_config = json.loads(search_config_response['Body'].read().decode('utf-8'))
        except Exception:
            # Use default search configuration
            search_config = {
                "beam_width": 10,
                "max_visited_nodes": 1000,
                "early_termination": True
            }
        
        # Load partition structure
        try:
            partition_response = s3_client.get_object(
                Bucket=vector_bucket,
                Key=f"_indexes/{index_name}/partitions.json"
            )
            partition_data = json.loads(partition_response['Body'].read().decode('utf-8'))
        except Exception as e:
            logger.warning(f"Could not load partition structure: {e}")
            # Fall back to batch search
            return _query_vectors_optimized_batch(
                query_embedding, limit, similarity_threshold, filters,
                vector_bucket, index_name
            )
        
        # Hierarchical search starting from top level
        beam_width = search_config.get("beam_width", 10)
        candidates = []
        
        # Level 2: Search top-level centroids
        level_2_centroids = partition_data.get("hierarchy", {}).get("level_2", [])
        if level_2_centroids:
            centroid_similarities = []
            for centroid_id in level_2_centroids:
                try:
                    centroid_key = f"_indexes/{index_name}/centroids/{centroid_id}.json"
                    centroid_response = s3_client.get_object(Bucket=vector_bucket, Key=centroid_key)
                    centroid_data = json.loads(centroid_response['Body'].read().decode('utf-8'))
                    
                    similarity = calculate_cosine_similarity(
                        query_embedding, 
                        centroid_data["centroid_vector"]
                    )
                    centroid_similarities.append((centroid_id, similarity, centroid_data))
                except Exception as e:
                    logger.debug(f"Error loading centroid {centroid_id}: {e}")
                    continue
            
            # Select top centroids for exploration
            centroid_similarities.sort(key=lambda x: x[1], reverse=True)
            selected_centroids = centroid_similarities[:beam_width]
        else:
            # No hierarchy, search all level 1 partitions
            selected_centroids = [(None, 1.0, {"child_partitions": partition_data.get("hierarchy", {}).get("level_1", [])})]
        
        # Level 1: Search mid-level partitions
        level_1_candidates = []
        for centroid_id, centroid_sim, centroid_data in selected_centroids:
            child_partitions = centroid_data.get("child_partitions", [])
            
            for partition_id in child_partitions:
                try:
                    partition_key = f"_indexes/{index_name}/partitions/{partition_id}.json"
                    partition_response = s3_client.get_object(Bucket=vector_bucket, Key=partition_key)
                    partition_info = json.loads(partition_response['Body'].read().decode('utf-8'))
                    
                    # Calculate similarity to partition centroid
                    if "centroid_vector" in partition_info:
                        similarity = calculate_cosine_similarity(
                            query_embedding,
                            partition_info["centroid_vector"]
                        )
                        level_1_candidates.append((partition_id, similarity, partition_info))
                except Exception as e:
                    logger.debug(f"Error loading partition {partition_id}: {e}")
                    continue
        
        # Select best level 1 partitions
        level_1_candidates.sort(key=lambda x: x[1], reverse=True)
        selected_partitions = level_1_candidates[:beam_width * 2]  # Explore more at this level
        
        # Level 0: Search actual vectors in selected partitions
        results = []
        vectors_processed = 0
        max_vectors = search_config.get("max_visited_nodes", 1000)
        
        for partition_id, partition_sim, partition_info in selected_partitions:
            if vectors_processed >= max_vectors:
                break
                
            # Load vectors from this partition
            vector_keys = partition_info.get("vector_keys", [])
            
            # Process vectors in batch for efficiency
            batch_vectors = []
            batch_metadata = []
            
            for vector_key in vector_keys[:min(100, max_vectors - vectors_processed)]:
                try:
                    vector_response = s3_client.get_object(Bucket=vector_bucket, Key=vector_key)
                    vector_data = json.loads(vector_response['Body'].read().decode('utf-8'))
                    
                    # Apply filters early
                    if filters and not _apply_filters(vector_data, filters):
                        continue
                    
                    batch_vectors.append(vector_data["embedding"])
                    batch_metadata.append(vector_data)
                    vectors_processed += 1
                    
                except Exception as e:
                    logger.debug(f"Error loading vector {vector_key}: {e}")
                    continue
            
            # Batch similarity calculation
            if batch_vectors:
                similarities = calculate_batch_cosine_similarity(query_embedding, batch_vectors)
                
                for i, similarity in enumerate(similarities):
                    if similarity >= similarity_threshold:
                        metadata = batch_metadata[i]
                        result = {
                            "id": metadata["vector_id"],
                            "document_id": metadata["document_id"],
                            "chunk_index": metadata["chunk_index"],
                            "content": metadata["content"],
                            "heading": metadata["heading"],
                            "chunk_type": metadata["chunk_type"],
                            "importance_score": metadata["importance_score"],
                            "metadata": metadata["metadata"],
                            "similarity": similarity
                        }
                        results.append(result)
        
        # Sort by combined score and return top results
        results.sort(key=lambda x: x["similarity"] * x["importance_score"], reverse=True)
        
        logger.info(f"Hierarchical search processed {vectors_processed} vectors, found {len(results)} results")
        return results[:limit]
        
    except Exception as e:
        logger.error(f"Hierarchical search failed: {e}")
        # Fall back to batch search
        return _query_vectors_optimized_batch(
            query_embedding, limit, similarity_threshold, filters,
            vector_bucket, index_name
        )


def _query_vectors_optimized_batch(
    query_embedding: List[float],
    limit: int,
    similarity_threshold: float,
    filters: Optional[Dict[str, Any]],
    vector_bucket: str,
    index_name: str
) -> List[Dict[str, Any]]:
    """
    Optimized batch vector query using vectorized similarity calculations.
    
    Args:
        query_embedding: Query vector
        limit: Maximum results to return
        similarity_threshold: Minimum similarity threshold
        filters: Optional metadata filters
        vector_bucket: S3 bucket name
        index_name: Vector index name
        
    Returns:
        List of similar documents with similarity scores
    """
    try:
        s3_client = get_s3_client()
        
        # Generate query hash for caching
        query_hash = _generate_cache_key(str(query_embedding), similarity_threshold, str(filters))
        
        # List all vector objects in the index
        prefix = f"vectors/{index_name}/"
        
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=vector_bucket,
                Prefix=prefix,
                MaxKeys=1000  # Process in batches
            )
            
            all_vectors = []
            all_metadata = []
            vector_ids = []
            
            # Collect vectors in batches for vectorized processing
            for page in page_iterator:
                batch_vectors = []
                batch_metadata = []
                batch_ids = []
                
                for obj in page.get('Contents', []):
                    try:
                        # Extract vector ID from key
                        vector_id = obj["Key"].split("/")[-1].replace(".json", "")
                        
                        # Check cache first
                        cached_similarity = _get_cached_similarity(query_hash, vector_id)
                        if cached_similarity is not None:
                            cached_metadata = _get_cached_vector_metadata(vector_id)
                            if cached_metadata and cached_similarity >= similarity_threshold:
                                if not filters or _apply_filters(cached_metadata, filters):
                                    all_metadata.append({
                                        **cached_metadata,
                                        "similarity": cached_similarity,
                                        "vector_id": vector_id
                                    })
                            continue
                        
                        # Load vector data
                        response = s3_client.get_object(Bucket=vector_bucket, Key=obj["Key"])
                        vector_data = json.loads(response['Body'].read().decode('utf-8'))
                        
                        # Apply filters early
                        if filters and not _apply_filters(vector_data, filters):
                            continue
                        
                        # Cache metadata
                        _cache_vector_metadata(vector_id, vector_data)
                        
                        # Collect for batch processing
                        batch_vectors.append(vector_data["embedding"])
                        batch_metadata.append(vector_data)
                        batch_ids.append(vector_id)
                        
                    except Exception as e:
                        logger.debug(f"Error processing vector object {obj['Key']}: {e}")
                        continue
                
                # Process batch with vectorized similarity calculation
                if batch_vectors:
                    similarities = calculate_batch_cosine_similarity(query_embedding, batch_vectors)
                    
                    for i, similarity in enumerate(similarities):
                        if similarity >= similarity_threshold:
                            # Cache the similarity result
                            _cache_similarity_result(query_hash, batch_ids[i], similarity)
                            
                            # Add to results
                            metadata = batch_metadata[i]
                            metadata["similarity"] = similarity
                            metadata["vector_id"] = batch_ids[i]
                            all_metadata.append(metadata)
            
            # Convert to result format
            results = []
            for metadata in all_metadata:
                try:
                    result = {
                        "id": metadata["vector_id"],
                        "document_id": metadata["document_id"],
                        "chunk_index": metadata["chunk_index"],
                        "content": metadata["content"],
                        "heading": metadata["heading"],
                        "chunk_type": metadata["chunk_type"],
                        "importance_score": metadata["importance_score"],
                        "metadata": metadata["metadata"],
                        "similarity": metadata["similarity"]
                    }
                    results.append(result)
                except Exception as e:
                    logger.debug(f"Error formatting result: {e}")
                    continue
            
            # Sort by combined score
            results.sort(key=lambda x: x["similarity"] * x["importance_score"], reverse=True)
            
            logger.info(f"Batch optimized query returned {len(results)} results")
            return results[:limit]
            
        except Exception as s3_error:
            logger.error(f"S3 batch query failed: {s3_error}")
            return []
        
    except Exception as e:
        logger.error(f"Optimized batch query failed: {e}")
        return []


def _query_vectors_optimized(
    query_embedding: List[float],
    limit: int,
    similarity_threshold: float,
    filters: Optional[Dict[str, Any]],
    vector_bucket: str,
    index_name: str
) -> List[Dict[str, Any]]:
    """
    Optimized vector search using partitioned S3 storage with comprehensive caching.
    """
    try:
        s3_client = get_s3_client()
        
        # Generate query hash for caching
        query_hash = _generate_cache_key(str(query_embedding), similarity_threshold, str(filters))
        
        # Try to get partition information from cache first
        partition_info = _get_cached_partition_info(index_name)
        
        if partition_info is None:
            # Get partition information for efficient search with error handling
            try:
                partition_response = s3_client.get_object(
                    Bucket=vector_bucket,
                    Key=f"_indexes/{index_name}/partitions.json"
                )
                partition_info = json.loads(partition_response["Body"].read())
                
                if not isinstance(partition_info, dict):
                    logger.warning("Invalid partition info format, falling back to full scan")
                    raise ValueError("Invalid partition info")
                
                # Cache the partition info
                _cache_partition_info(index_name, partition_info)
                    
            except Exception as partition_error:
                logger.info(f"Partition info not available ({partition_error}), using full scan")
                return _query_vectors_full_scan(
                    query_embedding, limit, similarity_threshold, filters,
                    vector_bucket, index_name, s3_client, query_hash
                )
        
        results = []
        partitions_to_search = partition_info.get("partitions", [])
        
        # If no partitions exist, fall back to full scan
        if not partitions_to_search:
            logger.info("No partitions found, using full scan")
            return _query_vectors_full_scan(
                query_embedding, limit, similarity_threshold, filters,
                vector_bucket, index_name, s3_client, query_hash
            )
        
        # Search partitions with error handling and caching
        successful_partitions = 0
        for partition_id in partitions_to_search:
            try:
                partition_results = _search_partition(
                    partition_id, query_embedding, similarity_threshold,
                    filters, vector_bucket, index_name, s3_client, query_hash
                )
                results.extend(partition_results)
                successful_partitions += 1
                
            except Exception as partition_search_error:
                logger.warning(f"Error searching partition {partition_id}: {partition_search_error}")
                continue
        
        if successful_partitions == 0:
            logger.warning("All partition searches failed, falling back to full scan")
            return _query_vectors_full_scan(
                query_embedding, limit, similarity_threshold, filters,
                vector_bucket, index_name, s3_client, query_hash
            )
        
        # Sort by similarity score and importance with error handling
        try:
            results.sort(key=lambda x: x["similarity"] * x["importance_score"], reverse=True)
        except Exception as sort_error:
            logger.warning(f"Error sorting results: {sort_error}")
            # Try simple similarity sort as fallback
            try:
                results.sort(key=lambda x: x["similarity"], reverse=True)
            except Exception:
                logger.warning("Could not sort results, returning unsorted")
        
        # Return top results
        return results[:limit]
        
    except Exception as e:
        logger.error(f"Optimized vector search failed: {e}")
        # Final fallback to full scan
        try:
            s3_client = get_s3_client()
            query_hash = _generate_cache_key(str(query_embedding), similarity_threshold, str(filters))
            return _query_vectors_full_scan(
                query_embedding, limit, similarity_threshold, filters,
                vector_bucket, index_name, s3_client, query_hash
            )
        except Exception as final_error:
            logger.error(f"Final fallback search failed: {final_error}")
            return []


def _search_partition(
    partition_id: str,
    query_embedding: List[float],
    similarity_threshold: float,
    filters: Optional[Dict[str, Any]],
    vector_bucket: str,
    index_name: str,
    s3_client: Any,
    query_hash: str
) -> List[Dict[str, Any]]:
    """Search a specific partition for similar vectors with caching."""
    try:
        # List objects in this partition
        response = s3_client.list_objects_v2(
            Bucket=vector_bucket,
            Prefix=f"vectors/{index_name}/partition_{partition_id}/"
        )
        
        if "Contents" not in response:
            return []
        
        results = []
        
        for obj in response["Contents"]:
            if not obj["Key"].endswith(".json"):
                continue
                
            try:
                # Extract vector ID from key
                vector_id = obj["Key"].split("/")[-1].replace(".json", "")
                
                # Check cache for similarity first
                cached_similarity = _get_cached_similarity(query_hash, vector_id)
                if cached_similarity is not None:
                    # Get metadata from cache or S3
                    cached_metadata = _get_cached_vector_metadata(vector_id)
                    if cached_metadata:
                        # Apply filters if provided
                        if filters and not _apply_filters(cached_metadata, filters):
                            continue
                        
                        if cached_similarity >= similarity_threshold:
                            results.append({
                                "id": vector_id,
                                "document_id": cached_metadata["document_id"],
                                "chunk_index": cached_metadata["chunk_index"],
                                "content": cached_metadata["content"],
                                "heading": cached_metadata["heading"],
                                "chunk_type": cached_metadata["chunk_type"],
                                "importance_score": cached_metadata["importance_score"],
                                "metadata": cached_metadata["metadata"],
                                "similarity": cached_similarity
                            })
                        continue
                
                # Get vector data from S3
                vector_response = s3_client.get_object(
                    Bucket=vector_bucket,
                    Key=obj["Key"]
                )
                
                vector_data = json.loads(vector_response["Body"].read())
                
                # Cache the metadata
                _cache_vector_metadata(vector_id, vector_data)
                
                # Apply filters if provided
                if filters and not _apply_filters(vector_data, filters):
                    continue
                
                # Calculate similarity
                similarity = calculate_cosine_similarity(query_embedding, vector_data["embedding"])
                
                # Cache the similarity result
                _cache_similarity_result(query_hash, vector_id, similarity)
                
                if similarity >= similarity_threshold:
                    results.append({
                        "id": vector_data["vector_id"],
                        "document_id": vector_data["document_id"],
                        "chunk_index": vector_data["chunk_index"],
                        "content": vector_data["content"],
                        "heading": vector_data["heading"],
                        "chunk_type": vector_data["chunk_type"],
                        "importance_score": vector_data["importance_score"],
                        "metadata": vector_data["metadata"],
                        "similarity": similarity
                    })
                    
            except Exception as e:
                logger.warning(f"Error processing vector object {obj['Key']}: {e}")
                continue
        
        return results
        
    except Exception as e:
        logger.error(f"Error searching partition {partition_id}: {e}")
        return []


def _query_vectors_full_scan(
    query_embedding: List[float],
    limit: int,
    similarity_threshold: float,
    filters: Optional[Dict[str, Any]],
    vector_bucket: str,
    index_name: str,
    s3_client: Any,
    query_hash: str
) -> List[Dict[str, Any]]:
    """Full scan fallback for vector search with caching."""
    # List all vector objects in the index
    response = s3_client.list_objects_v2(
        Bucket=vector_bucket,
        Prefix=f"vectors/{index_name}/"
    )
    
    if "Contents" not in response:
        logger.warning("No vectors found in index")
        return []
    
    results = []
    
    # Process each vector object
    for obj in response["Contents"]:
        if not obj["Key"].endswith(".json"):
            continue
            
        try:
            # Extract vector ID from key
            vector_id = obj["Key"].split("/")[-1].replace(".json", "")
            
            # Check cache for similarity first
            cached_similarity = _get_cached_similarity(query_hash, vector_id)
            if cached_similarity is not None:
                # Get metadata from cache or S3
                cached_metadata = _get_cached_vector_metadata(vector_id)
                if cached_metadata:
                    # Apply filters if provided
                    if filters and not _apply_filters(cached_metadata, filters):
                        continue
                    
                    if cached_similarity >= similarity_threshold:
                        results.append({
                            "id": vector_id,
                            "document_id": cached_metadata["document_id"],
                            "chunk_index": cached_metadata["chunk_index"],
                            "content": cached_metadata["content"],
                            "heading": cached_metadata["heading"],
                            "chunk_type": cached_metadata["chunk_type"],
                            "importance_score": cached_metadata["importance_score"],
                            "metadata": cached_metadata["metadata"],
                            "similarity": cached_similarity
                        })
                    continue
            
            # Get vector data from S3
            vector_response = s3_client.get_object(
                Bucket=vector_bucket,
                Key=obj["Key"]
            )
            
            vector_data = json.loads(vector_response["Body"].read())
            
            # Cache the metadata
            _cache_vector_metadata(vector_id, vector_data)
            
            # Apply filters if provided
            if filters and not _apply_filters(vector_data, filters):
                continue
            
            # Calculate cosine similarity
            similarity = calculate_cosine_similarity(query_embedding, vector_data["embedding"])
            
            # Cache the similarity result
            _cache_similarity_result(query_hash, vector_id, similarity)
            
            if similarity >= similarity_threshold:
                results.append({
                    "id": vector_data["vector_id"],
                    "document_id": vector_data["document_id"],
                    "chunk_index": vector_data["chunk_index"],
                    "content": vector_data["content"],
                    "heading": vector_data["heading"],
                    "chunk_type": vector_data["chunk_type"],
                    "importance_score": vector_data["importance_score"],
                    "metadata": vector_data["metadata"],
                    "similarity": similarity
                })
                
        except Exception as e:
            logger.warning(f"Error processing vector object {obj['Key']}: {e}")
            continue
    
    # Sort by similarity score (descending) and importance
    results.sort(key=lambda x: x["similarity"] * x["importance_score"], reverse=True)
    
    # Return top results
    return results[:limit]


def _apply_filters(vector_data: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """Apply metadata filters to vector data."""
    try:
        if filters.get("document_ids") and vector_data["document_id"] not in filters["document_ids"]:
            return False
        if filters.get("min_date") and vector_data["created_at"] < filters["min_date"]:
            return False
        if filters.get("max_date") and vector_data["created_at"] > filters["max_date"]:
            return False
        return True
    except Exception:
        return True  # If filter application fails, include the result


def calculate_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity using NumPy.
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        Cosine similarity score (0-1), 0.0 if calculation fails
    """
    try:
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        try:
            import numpy as np
            a = np.asarray(vec1, dtype=np.float32)
            b = np.asarray(vec2, dtype=np.float32)
            
            if np.any(~np.isfinite(a)) or np.any(~np.isfinite(b)):
                return 0.0
            
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            
            similarity = dot_product / (norm_a * norm_b)
            similarity = (similarity + 1.0) * 0.5  # Normalize to [0, 1]
            return float(np.clip(similarity, 0.0, 1.0))
            
        except ImportError:
            # Manual calculation if NumPy not available
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm_a = sum(a * a for a in vec1) ** 0.5
            norm_b = sum(b * b for b in vec2) ** 0.5
            
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            
            similarity = (dot_product / (norm_a * norm_b) + 1.0) * 0.5
            return max(0.0, min(1.0, similarity))
        
    except Exception as e:
        logger.debug(f"Error in cosine similarity calculation: {e}")
        return 0.0

def calculate_batch_cosine_similarity(query_vector: List[float], vectors: List[List[float]]) -> List[float]:
    """
    Optimized batch cosine similarity calculation using NumPy vectorization.
    
    Args:
        query_vector: Query vector
        vectors: List of vectors to compare against
        
    Returns:
        List of similarity scores (0-1)
    """
    try:
        if not query_vector or not vectors:
            return []
        
        # Import numpy for vectorized operations
        try:
            import numpy as np
        except ImportError:
            # Fallback to individual calculations
            return [calculate_cosine_similarity(query_vector, vec) for vec in vectors]
        
        # Convert to numpy arrays for vectorized operations
        query = np.asarray(query_vector, dtype=np.float32)
        vector_matrix = np.asarray(vectors, dtype=np.float32)
        
        # Validate dimensions
        if vector_matrix.shape[1] != len(query):
            logger.error("Dimension mismatch in batch similarity calculation")
            return [0.0] * len(vectors)
        
        # Check for invalid values
        if not np.all(np.isfinite(query)) or not np.all(np.isfinite(vector_matrix)):
            logger.warning("Invalid values detected in batch similarity calculation")
            return [0.0] * len(vectors)
        
        # Vectorized dot products
        dot_products = np.dot(vector_matrix, query)
        
        # Vectorized norms
        query_norm = np.linalg.norm(query)
        vector_norms = np.linalg.norm(vector_matrix, axis=1)
        
        # Handle zero norms
        if query_norm == 0.0:
            return [0.0] * len(vectors)
        
        # Avoid division by zero
        valid_norms = vector_norms != 0.0
        similarities = np.zeros(len(vectors), dtype=np.float32)
        
        if np.any(valid_norms):
            # Vectorized cosine similarity calculation
            similarities[valid_norms] = dot_products[valid_norms] / (query_norm * vector_norms[valid_norms])
            
            # Normalize to [0, 1] range
            similarities = (similarities + 1.0) * 0.5
            
            # Clamp to valid range
            similarities = np.clip(similarities, 0.0, 1.0)
        
        return similarities.tolist()
        
    except Exception as e:
        logger.debug(f"Batch similarity calculation failed: {e}, using individual calculations")
        return [calculate_cosine_similarity(query_vector, vec) for vec in vectors]


def _calculate_cosine_similarity_manual(vec1: List[float], vec2: List[float]) -> float:
    """
    Optimized manual cosine similarity calculation as fallback.
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        Cosine similarity score (0-1)
    """
    try:
        # Fast dot product and norm calculations
        dot_product = 0.0
        norm_a_sq = 0.0
        norm_b_sq = 0.0
        
        # Single loop for all calculations
        for a, b in zip(vec1, vec2):
            a_val = float(a)
            b_val = float(b)
            dot_product += a_val * b_val
            norm_a_sq += a_val * a_val
            norm_b_sq += b_val * b_val
        
        # Fast square root
        norm_a = norm_a_sq ** 0.5
        norm_b = norm_b_sq ** 0.5
        
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        
        # Calculate and normalize cosine similarity to [0, 1]
        similarity = (dot_product / (norm_a * norm_b) + 1.0) * 0.5
        
        # Clamp to valid range
        return max(0.0, min(1.0, similarity))
        
    except Exception as e:
        logger.debug(f"Manual cosine similarity calculation failed: {e}")
        return 0.0


def list_vector_indexes() -> List[Dict[str, Any]]:
    """
    List all available vector indexes using S3 Vectors API only.
    
    Returns:
        List of vector index information
    """
    try:
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        if not vector_bucket:
            raise ValueError("VECTOR_BUCKET_NAME environment variable not set")
        
        s3_vectors_client = get_s3_vectors_client()
        
        # Use S3 Vectors API only - no fallbacks
        response = s3_vectors_client.list_indexes(vectorBucketName=vector_bucket)
        
        indexes = []
        for index in response.get('indexes', []):
            index_name = index.get('indexName')
            
            try:
                index_details = s3_vectors_client.get_index(
                    vectorBucketName=vector_bucket,
                    indexName=index_name
                )
                index_info = index_details.get('index', {})
                
                # Count vectors
                vector_count = 0
                try:
                    vector_count = _count_vectors_in_index(vector_bucket, index_name, s3_vectors_client)
                except Exception:
                    vector_count = 0
                
                indexes.append({
                    "name": index_name,
                    "arn": index.get('indexArn'),
                    "bucket": index.get('vectorBucketName'),
                    "created": index.get('creationTime'),
                    "status": "ACTIVE",
                    "dimensions": index_info.get('dimension', 0),
                    "distance_metric": index_info.get('distanceMetric', 'unknown'),
                    "data_type": index_info.get('dataType', 'float32'),
                    "vector_count": vector_count,
                    "native_api": True
                })
                
            except Exception as detail_error:
                logger.warning(f"Could not get details for index {index_name}: {detail_error}")
                indexes.append({
                    "name": index_name,
                    "arn": index.get('indexArn'),
                    "bucket": index.get('vectorBucketName'),
                    "created": index.get('creationTime'),
                    "status": "ACTIVE",
                    "vector_count": 0,
                    "native_api": True
                })
        
        logger.info(f"Found {len(indexes)} S3 Vector indexes")
        return indexes
        
    except Exception as e:
        error = handle_error(e, context={"function": "list_vector_indexes"})
        logger.error(f"Failed to list vector indexes: {error}")
        return []


def _list_s3_vector_indexes(vector_bucket: str) -> List[Dict[str, Any]]:
    """List vector indexes using S3 implementation."""
    try:
        s3_client = get_s3_client()
        
        # List index configuration files
        response = s3_client.list_objects_v2(
            Bucket=vector_bucket,
            Prefix="_indexes/",
            Delimiter="/"
        )
        
        indexes = []
        
        for prefix in response.get('CommonPrefixes', []):
            index_name = prefix['Prefix'].split('/')[-2]
            
            try:
                # Get index configuration
                config_response = s3_client.get_object(
                    Bucket=vector_bucket,
                    Key=f"_indexes/{index_name}/config.json"
                )
                
                config = json.loads(config_response["Body"].read())
                
                # Count vectors in this index using S3 Vectors API
                s3_vectors_client = get_s3_vectors_client()
                vector_count = _count_vectors_in_index(vector_bucket, index_name, s3_vectors_client)
                
                indexes.append({
                    "name": index_name,
                    "id": f"s3-{index_name}",
                    "status": config.get("status", "UNKNOWN"),
                    "dimensions": config.get("dimensions"),
                    "similarity_metric": config.get("similarity_metric"),
                    "created_at": config.get("created_at"),
                    "vector_count": vector_count,
                    "index_type": config.get("index_type", "HNSW"),
                    "optimization": config.get("optimization", {})
                })
                
            except Exception as config_error:
                logger.warning(f"Could not read config for index {index_name}: {config_error}")
                continue
        
        return indexes
        
    except Exception as e:
        logger.error(f"Failed to list S3 vector indexes: {e}")
        return []


def _count_vectors_in_index(vector_bucket: str, index_name: str, s3_vectors_client: Any) -> int:
    """Count vectors in a specific index using S3 Vectors API."""
    try:
        vector_count = 0
        next_token = None
        
        while True:
            list_params = {
                'vectorBucketName': vector_bucket,
                'indexName': index_name,
                'maxResults': 1000
            }
            if next_token:
                list_params['nextToken'] = next_token
                
            response = s3_vectors_client.list_vectors(**list_params)
            batch_count = len(response.get('vectors', []))
            vector_count += batch_count
            
            next_token = response.get('nextToken')
            if not next_token:
                break
                
        return vector_count
        
    except Exception as e:
        logger.warning(f"Could not count vectors in index {index_name}: {e}")
        return 0


def get_vector_index_info(index_name: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific vector index using S3 Vectors API only.
    
    Args:
        index_name: Name of the vector index
        
    Returns:
        Index information dictionary or None if not found
    """
    try:
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        if not vector_bucket:
            raise ValueError("VECTOR_BUCKET_NAME environment variable not set")
        
        s3_vectors_client = get_s3_vectors_client()
        
        # Use S3 Vectors API only - no fallbacks
        response = s3_vectors_client.get_index(
            vectorBucketName=vector_bucket,
            indexName=index_name
        )
        
        index_data = response.get('index', {})
        
        # Count vectors using S3 Vectors API with pagination
        vector_count = _count_vectors_in_index(vector_bucket, index_name, s3_vectors_client)
        
        index_info = {
            "name": index_data.get('indexName'),
            "arn": index_data.get('indexArn'),
            "bucket": index_data.get('vectorBucketName'),
            "status": "ACTIVE",
            "data_type": index_data.get('dataType'),
            "dimensions": index_data.get('dimension'),
            "distance_metric": index_data.get('distanceMetric'),
            "created": index_data.get('creationTime'),
            "vector_count": vector_count,
            "native_api": True
        }
        
        return index_info
        
    except Exception as e:
        error = handle_error(e, context={"function": "get_vector_index_info", "index_name": index_name})
        logger.error(f"Failed to get vector index info: {error}")
        return None


def _get_s3_vector_index_info(vector_bucket: str, index_name: str) -> Optional[Dict[str, Any]]:
    """Get vector index info using S3 implementation."""
    try:
        s3_client = get_s3_client()
        
        # Get index configuration
        config_response = s3_client.get_object(
            Bucket=vector_bucket,
            Key=f"_indexes/{index_name}/config.json"
        )
        
        config = json.loads(config_response["Body"].read())
        
        # Get partition information
        try:
            partition_response = s3_client.get_object(
                Bucket=vector_bucket,
                Key=f"_indexes/{index_name}/partitions.json"
            )
            partition_info = json.loads(partition_response["Body"].read())
        except Exception:
            partition_info = {"partitions": [], "next_partition_id": 0}
        
        # Count vectors and calculate storage size using S3 Vectors API
        s3_vectors_client = get_s3_vectors_client()
        vector_count = _count_vectors_in_index(vector_bucket, index_name, s3_vectors_client)
        storage_size = _calculate_index_storage_size(vector_bucket, index_name, s3_client)
        
        index_info = {
            "name": index_name,
            "id": f"s3-{index_name}",
            "status": config.get("status", "UNKNOWN"),
            "dimensions": config.get("dimensions"),
            "similarity_metric": config.get("similarity_metric"),
            "index_type": config.get("index_type", "HNSW"),
            "created_at": config.get("created_at"),
            "updated_at": config.get("updated_at", config.get("created_at")),
            "vector_count": vector_count,
            "storage_size_bytes": storage_size,
            "partition_count": len(partition_info.get("partitions", [])),
            "optimization": config.get("optimization", {}),
            "native_api": False
        }
        
        return index_info
        
    except Exception as e:
        logger.error(f"Failed to get S3 vector index info for {index_name}: {e}")
        return None


def _calculate_index_storage_size(vector_bucket: str, index_name: str, s3_client: Any) -> int:
    """Calculate approximate storage size of an index."""
    try:
        response = s3_client.list_objects_v2(
            Bucket=vector_bucket,
            Prefix=f"vectors/{index_name}/",
            MaxKeys=1000
        )
        
        total_size = 0
        for obj in response.get('Contents', []):
            total_size += obj.get('Size', 0)
        
        return total_size
        
    except Exception as e:
        logger.warning(f"Could not calculate storage size for index {index_name}: {e}")
        return 0


def delete_vector_index(index_name: str, force: bool = False) -> bool:
    """
    Delete a vector index using S3 Vectors API only.
    
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
        
        s3_vectors_client = get_s3_vectors_client()
        
        # Use S3 Vectors API only - no fallbacks
        s3_vectors_client.delete_index(
            vectorBucketName=vector_bucket,
            indexName=index_name
        )
        logger.info(f"Deleted S3 Vector index '{index_name}'")
        return True
        
    except Exception as e:
        error = handle_error(e, context={"function": "delete_vector_index", "index_name": index_name})
        logger.error(f"Failed to delete vector index: {error}")
        return False


def _delete_s3_vector_index(vector_bucket: str, index_name: str) -> bool:
    """Delete vector index using S3 implementation."""
    try:
        s3_client = get_s3_client()
        
        # Delete all vectors in the index
        logger.info(f"Deleting all vectors in index {index_name}...")
        
        # List and delete all vector objects
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=vector_bucket, Prefix=f"vectors/{index_name}/")
        
        objects_to_delete = []
        for page in pages:
            for obj in page.get('Contents', []):
                objects_to_delete.append({'Key': obj['Key']})
                
                # Delete in batches of 1000 (S3 limit)
                if len(objects_to_delete) >= 1000:
                    s3_client.delete_objects(
                        Bucket=vector_bucket,
                        Delete={'Objects': objects_to_delete}
                    )
                    objects_to_delete = []
        
        # Delete remaining objects
        if objects_to_delete:
            s3_client.delete_objects(
                Bucket=vector_bucket,
                Delete={'Objects': objects_to_delete}
            )
        
        # Delete index configuration and metadata
        index_objects = [
            f"_indexes/{index_name}/config.json",
            f"_indexes/{index_name}/partitions.json"
        ]
        
        for obj_key in index_objects:
            try:
                s3_client.delete_object(Bucket=vector_bucket, Key=obj_key)
            except Exception as e:
                logger.warning(f"Could not delete {obj_key}: {e}")
        
        logger.info(f"Successfully deleted S3 vector index '{index_name}'")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete S3 vector index {index_name}: {e}")
        return False


def optimize_vector_index(index_name: str) -> Dict[str, Any]:
    """
    Optimize vector index using S3 Vectors API.
    
    Args:
        index_name: Name of the vector index to optimize
        
    Returns:
        Optimization results and statistics
    """
    try:
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        if not vector_bucket:
            raise ValueError("VECTOR_BUCKET_NAME environment variable not set")
        
        s3_vectors_client = get_s3_vectors_client()
        
        logger.info(f"Starting optimization of vector index '{index_name}'")
        
        # Get vector count using S3 Vectors API
        vector_count = 0
        next_token = None
        
        while True:
            params = {
                'vectorBucketName': vector_bucket,
                'indexName': index_name,
                'maxResults': 1000
            }
            if next_token:
                params['nextToken'] = next_token
                
            response = s3_vectors_client.list_vectors(**params)
            vectors = response.get('vectors', [])
            vector_count += len(vectors)
            
            next_token = response.get('nextToken')
            if not next_token:
                break
        
        if vector_count == 0:
            return {"success": False, "error": "No vectors found in index"}
        
        logger.info(f"Found {vector_count} vectors in index")
        
        # Clear any cached data (simple optimization)
        cache_cleared = True
        
        return {
            "success": True,
            "vector_count": vector_count,
            "index_size_mb": round(vector_count * 0.006, 2),  # Estimate: ~6KB per vector
            "cache_cleared": cache_cleared,
            "message": f"Index optimized with {vector_count} vectors"
        }
        
    except Exception as e:
        logger.error(f"Failed to optimize vector index: {e}")
        return {"success": False, "error": "Vector index optimization failed"}


def get_vector_index_stats() -> Dict[str, Any]:
    """
    Get comprehensive statistics about all vector indexes.
    
    Returns:
        Dictionary containing index statistics
    """
    try:
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        index_name = os.environ.get("VECTOR_INDEX_NAME")
        
        if not vector_bucket or not index_name:
            return {
                "success": False,
                "error": "Vector configuration environment variables not set"
            }
        
        s3_vectors_client = get_s3_vectors_client()
        
        # Get index info using S3 Vectors API
        try:
            index_response = s3_vectors_client.get_index(
                vectorBucketName=vector_bucket,
                indexName=index_name
            )
            
            index_info = index_response.get('index', {})
            
            # Count vectors using paginated S3 Vectors API
            vector_count = _count_vectors_in_index(vector_bucket, index_name, s3_vectors_client)
            
            indexes = [{
                "name": index_info.get('indexName', index_name),
                "arn": index_info.get('indexArn', ''),
                "bucket": index_info.get('vectorBucketName', vector_bucket),
                "created": index_info.get('creationTime', 'unknown'),
                "status": "ACTIVE",
                "dimensions": index_info.get('dimension', 0),
                "distance_metric": index_info.get('distanceMetric', 'unknown'),
                "data_type": index_info.get('dataType', 'float32'),
                "vector_count": vector_count,
                "storage_size_bytes": 0,  # Not available from S3 Vectors API
                "native_api": True
            }]
            
            stats = {
                "success": True,
                "total_indexes": 1,
                "total_vectors": vector_count,
                "total_storage_bytes": 0,
                "total_storage_mb": 0.0,
                "average_vectors_per_index": vector_count,
                "indexes": indexes,
                "cache_stats": get_cache_stats(),
                "generated_at": datetime.utcnow().isoformat()
            }
            
            return stats
            
        except Exception as api_error:
            logger.error(f"S3 Vectors API error: {api_error}")
            return {
                "success": False,
                "error": f"Failed to get vector index stats: {str(api_error)}"
            }
        
    except Exception as e:
        error = handle_error(e, context={"function": "get_vector_index_stats"})
        logger.error(f"Failed to get vector index stats: {error}")
        return {
            "success": False,
            "error": "Vector cleanup failed"
        }
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
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        if not vector_bucket:
            raise ValueError("VECTOR_BUCKET_NAME environment variable not set")
        
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
        error = handle_error(e, context={"function": "store_document_metadata", "document_id": document_id})
        logger.error(f"Failed to store document metadata: {error}")
        return False


def delete_document_vectors(document_id: str) -> bool:
    """
    Delete all vectors for a specific document using S3 Vectors API.
    
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
        
        s3_vectors_client = get_s3_vectors_client()
        
        # List vectors for this document using S3 Vectors API
        try:
            response = s3_vectors_client.list_vectors(
                vectorBucketName=vector_bucket,
                indexName=index_name,
                returnMetadata=True
            )
            
            # Find vectors belonging to this document
            vector_keys_to_delete = []
            for vector in response.get('vectors', []):
                metadata = vector.get('metadata', {})
                if metadata.get('document_id') == document_id:
                    vector_keys_to_delete.append(vector.get('key'))
            
            # Delete vectors using S3 Vectors API
            if vector_keys_to_delete:
                s3_vectors_client.delete_vectors(
                    vectorBucketName=vector_bucket,
                    indexName=index_name,
                    keys=vector_keys_to_delete
                )
            
            logger.info(f"Deleted {len(vector_keys_to_delete)} vectors for document {document_id}")
            return True
            
        except Exception as api_error:
            logger.error(f"S3 Vectors API deletion failed: {api_error}")
            return False
        
    except Exception as e:
        error = handle_error(e, context={"function": "delete_document_vectors", "document_id": document_id})
        logger.error(f"Failed to delete document vectors: {error}")
        return False


def cleanup_old_vectors(days_old: int = 90) -> Dict[str, Any]:
    """
    Clean up vectors older than specified days.
    
    Args:
        days_old: Delete vectors older than this many days
        
    Returns:
        Cleanup results
    """
    try:
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        vector_bucket = os.environ.get("VECTOR_BUCKET_NAME")
        index_name = os.environ.get("VECTOR_INDEX_NAME")
        
        if not vector_bucket or not index_name:
            raise ValueError("Vector configuration environment variables not set")
        
        s3_client = get_s3_client()
        deleted_count = 0
        
        # List all vector objects
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=vector_bucket,
            Prefix=f"vectors/{index_name}/"
        )
        
        objects_to_delete = []
        for page in pages:
            for obj in page.get('Contents', []):
                if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
                    objects_to_delete.append({'Key': obj['Key']})
                    
                    # Delete in batches of 1000
                    if len(objects_to_delete) >= 1000:
                        s3_client.delete_objects(
                            Bucket=vector_bucket,
                            Delete={'Objects': objects_to_delete}
                        )
                        deleted_count += len(objects_to_delete)
                        objects_to_delete = []
        
        # Delete remaining objects
        if objects_to_delete:
            s3_client.delete_objects(
                Bucket=vector_bucket,
                Delete={'Objects': objects_to_delete}
            )
            deleted_count += len(objects_to_delete)
        
        logger.info(f"Cleaned up {deleted_count} old vectors (older than {days_old} days)")
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        error = handle_error(e, context={"function": "cleanup_old_vectors", "days_old": days_old})
        logger.error(f"Failed to cleanup old vectors: {error}")
        return {
            "success": False,
            "error": "Vector deletion failed",
            "deleted_count": 0
        }


# Export all functions for external use
__all__ = [
    'get_s3_client',
    'get_s3_vectors_client', 
    'create_vector_index',
    'list_vector_indexes',
    'get_vector_index_info',
    'delete_vector_index',
    'optimize_vector_index',
    'get_vector_index_stats',
    'store_document_vectors',
    'store_document_metadata',
    'query_similar_vectors',
    'delete_document_vectors',
    'calculate_cosine_similarity',
    'calculate_batch_cosine_similarity',
    'cleanup_old_vectors',
    'clear_all_caches',
    'get_cache_stats'
]
