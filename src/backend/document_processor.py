"""
Consolidated document processor Lambda function for the chatbot backend with S3 Vector storage.
Handles both synchronous and asynchronous document processing with batch optimization.
"""
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

try:
    from .bedrock_utils import generate_embeddings
    from .aws_utils import get_aws_region
    from .chunking import create_chunks
    from .document_utils import extract_text_from_document
    from .error_handler import (
        handle_error, create_error_response, create_success_response,
        ChatbotError, DatabaseError, BedrockError, ValidationError
    )
    from .s3_vector_utils import (
        create_vector_index,
        store_document_vectors,
        store_document_metadata,
        delete_document_vectors
    )
except ImportError:
    from bedrock_utils import generate_embeddings
    from aws_utils import get_aws_region
    from chunking import create_chunks
    from document_utils import extract_text_from_document
    from error_handler import (
        handle_error, create_error_response, create_success_response,
        ChatbotError, DatabaseError, BedrockError, ValidationError
    )
    from s3_vector_utils import (
        create_vector_index,
        store_document_vectors,
        store_document_metadata,
        delete_document_vectors
    )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def with_retry(func, max_retries: int = 3, backoff_factor: float = 1.0):
    """
    Retry decorator with exponential backoff.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retries
        backoff_factor: Backoff multiplier
        
    Returns:
        Function result or raises last exception
    """
    def wrapper(*args, **kwargs):
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt == max_retries:
                    break
                
                # Check if error is retryable
                if not _is_retryable_error(e):
                    break
                
                # Calculate backoff delay
                delay = backoff_factor * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
        
        raise last_exception
    
    return wrapper


def _is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable."""
    error_name = error.__class__.__name__
    error_message = str(error).lower()
    
    # Retryable errors
    retryable_errors = [
        "throttlingexception",
        "serviceunavailableexception",
        "internalservererror",
        "timeout",
        "connectionerror",
        "temporaryerror"
    ]
    
    return (
        error_name.lower() in retryable_errors or
        any(keyword in error_message for keyword in ["throttl", "timeout", "connection", "temporary"])
    )


@with_retry
def process_document(bucket: str, key: str) -> Dict[str, Any]:
    """
    Process document and store embeddings in S3 Vectors.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        
    Returns:
        Processing result
    """
    processing_result = {
        "success": False,
        "document_key": key,
        "document_id": None,
        "chunks_processed": 0,
        "total_chunks": 0,
        "processing_time": 0,
        "errors": [],
        "warnings": []
    }
    
    start_time = time.time()
    
    try:
        logger.info(f"Starting document processing for {key}")
        
        # Input validation
        if not bucket or not key:
            raise ValidationError("Bucket and key are required")
        
        # Validate file type
        file_extension = key.lower().split('.')[-1] if '.' in key else ''
        supported_extensions = ['pdf', 'txt', 'md', 'html', 'htm', 'csv', 'json', 'docx']
        
        if file_extension not in supported_extensions:
            raise ValidationError(f"Unsupported file type: {file_extension}")
        
        # Generate unique document ID
        document_id = str(uuid.uuid4())
        processing_result["document_id"] = document_id
        
        # Extract text and metadata from document
        extracted_content = extract_text_from_document(bucket, key)
        
        if not extracted_content.get("content"):
            processing_result["warnings"].append(f"No content extracted from {key}")
            return processing_result
        
        # Store document metadata
        metadata = {
            "filename": key,
            "document_id": document_id,
            "content_type": extracted_content.get("content_type", "unknown"),
            "file_size": extracted_content.get("file_size", 0),
            "content_length": len(extracted_content["content"]),
            "metadata": extracted_content.get("metadata", {}),
            "created_at": datetime.utcnow().isoformat(),
            "processing_status": "processing"
        }
        
        if not store_document_metadata(document_id, metadata):
            raise DatabaseError("Failed to store document metadata")
        
        # Create chunks from the document content
        chunks = create_chunks(
            extracted_content["content"],
            metadata=metadata,
            max_chunk_size=1000,
            overlap_size=100
        )
        
        if not chunks:
            processing_result["warnings"].append("No chunks created from document")
            return processing_result
        
        processing_result["total_chunks"] = len(chunks)
        logger.info(f"Created {len(chunks)} chunks for document {key}")
        
        # Process chunks in batches for better performance
        batch_size = 10
        processed_chunks = 0
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            # Generate embeddings for the batch
            batch_texts = [chunk["content"] for chunk in batch]
            try:
                embeddings = generate_embeddings(batch_texts)
            except Exception as e:
                logger.error(f"Failed to generate embeddings for batch: {e}")
                processing_result["errors"].append("Embedding generation failed")
                continue
            
            # Store vectors for each chunk in the batch
            for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
                try:
                    vector_data = {
                        "document_id": document_id,
                        "chunk_id": f"{document_id}_{i+j}",
                        "content": chunk["content"],
                        "embedding": embedding,
                        "metadata": {
                            **chunk.get("metadata", {}),
                            "chunk_index": i + j,
                            "document_filename": key
                        }
                    }
                    
                    if store_document_vectors(document_id, [vector_data]):
                        processed_chunks += 1
                    else:
                        processing_result["errors"].append(f"Failed to store vector for chunk {i+j}")
                        
                except Exception as e:
                    logger.error(f"Error processing chunk {i+j}: {e}")
                    processing_result["errors"].append(f"Chunk {i+j} processing failed")
        
        processing_result["chunks_processed"] = processed_chunks
        processing_result["processing_time"] = time.time() - start_time
        
        # Update metadata with final status
        metadata["processing_status"] = "completed" if processed_chunks > 0 else "failed"
        metadata["chunks_processed"] = processed_chunks
        metadata["processing_time"] = processing_result["processing_time"]
        store_document_metadata(document_id, metadata)
        
        if processed_chunks > 0:
            processing_result["success"] = True
            logger.info(f"Successfully processed {processed_chunks}/{len(chunks)} chunks for {key}")
        else:
            logger.error(f"Failed to process any chunks for {key}")
        
        return processing_result
        
    except Exception as e:
        processing_result["processing_time"] = time.time() - start_time
        processing_result["errors"].append("Document processing failed")
        logger.error(f"Document processing failed for {key}: {e}")
        return processing_result


def process_batch_documents(documents: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Process multiple documents in batch.
    
    Args:
        documents: List of documents with 'bucket' and 'key' fields
        
    Returns:
        Batch processing result
    """
    batch_result = {
        "success": True,
        "total_documents": len(documents),
        "processed_documents": 0,
        "failed_documents": 0,
        "results": [],
        "errors": []
    }
    
    logger.info(f"Starting batch processing of {len(documents)} documents")
    
    for doc in documents:
        try:
            result = process_document(doc["bucket"], doc["key"])
            batch_result["results"].append(result)
            
            if result["success"]:
                batch_result["processed_documents"] += 1
            else:
                batch_result["failed_documents"] += 1
                batch_result["errors"].extend(result["errors"])
                
        except Exception as e:
            batch_result["failed_documents"] += 1
            batch_result["errors"].append(f"Failed to process {doc['key']}")
            logger.error(f"Batch processing error for {doc['key']}: {e}")
    
    batch_result["success"] = batch_result["failed_documents"] == 0
    logger.info(f"Batch processing completed: {batch_result['processed_documents']}/{batch_result['total_documents']} successful")
    
    return batch_result


def handler(event, context):
    """
    Lambda handler for document processing.
    Supports both S3 events and direct invocation.
    """
    try:
        logger.info(f"Document processor invoked with event: {json.dumps(event, default=str)}")
        
        # Handle S3 event (automatic processing)
        if "Records" in event:
            results = []
            
            for record in event["Records"]:
                if record.get("eventSource") == "aws:s3":
                    bucket = record["s3"]["bucket"]["name"]
                    key = record["s3"]["object"]["key"]
                    
                    # Skip processing for non-document files
                    if not _is_document_file(key):
                        logger.info(f"Skipping non-document file: {key}")
                        continue
                    
                    result = process_document(bucket, key)
                    results.append(result)
            
            return create_success_response({
                "message": f"Processed {len(results)} documents from S3 events",
                "results": results
            })
        
        # Handle direct invocation
        elif "bucket" in event and "key" in event:
            result = process_document(event["bucket"], event["key"])
            return create_success_response(result)
        
        # Handle batch processing
        elif "documents" in event:
            result = process_batch_documents(event["documents"])
            return create_success_response(result)
        
        else:
            raise ValidationError("Invalid event format. Expected S3 event, direct invocation, or batch processing.")
    
    except Exception as e:
        logger.error(f"Document processor handler error: {e}")
        return create_error_response("Document processing failed", 500)


def _is_document_file(key: str) -> bool:
    """Check if the file is a supported document type."""
    if not key or '.' not in key:
        return False
    
    extension = key.lower().split('.')[-1]
    supported_extensions = ['pdf', 'txt', 'md', 'html', 'htm', 'csv', 'json', 'docx']
    
    return extension in supported_extensions


# For backward compatibility
async_handler = handler  # Alias for async processing
get_async_processor = lambda: handler  # Alias for getting processor
