#!/usr/bin/env python3
"""
Local document processing script with full functionality.
This script processes documents locally and uploads the results to S3.
"""

import argparse
import json
import logging
import os
import sys
import time
import re
from pathlib import Path
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import required libraries
import boto3
import numpy as np
from scipy.spatial.distance import cosine
import nltk
from nltk.tokenize import sent_tokenize

# Download NLTK data if needed
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Document processing imports
try:
    import PyPDF2
    from docx import Document
    from PIL import Image
    import textstat
except ImportError as e:
    logger.warning(f"Some document processing libraries not available: {e}")

class LocalDocumentProcessor:
    """Local document processor with full functionality."""
    
    def __init__(self, config_path: str = None):
        """Initialize the processor."""
        self.config = self._load_config(config_path)
        self.region = self._get_aws_region()
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=self.region)
        self.s3_client = boto3.client('s3', region_name=self.region)
        
    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load configuration from file."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.json"
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            # Normalize config structure
            normalized_config = {
                "bedrock": {
                    "modelId": config.get("bedrock", {}).get("modelId", "amazon.nova-lite-v1:0"),
                    "embeddingModelId": "amazon.titan-embed-text-v2:0"
                },
                "vectorIndex": {
                    "name": config.get("s3Vectors", {}).get("indexName", "chatbot-vectors"),
                    "dimensions": config.get("s3Vectors", {}).get("dimensions", 1536)
                }
            }
            return normalized_config
            
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            # Return default config
            return {
                "bedrock": {
                    "modelId": "amazon.nova-lite-v1:0",
                    "embeddingModelId": "amazon.titan-embed-text-v2:0"
                },
                "vectorIndex": {
                    "name": "chatbot-vectors",
                    "dimensions": 1536
                }
            }
    
    def _get_aws_region(self) -> str:
        """Get AWS region."""
        return os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
    
    def _extract_text_from_file(self, file_path: str) -> str:
        """Extract text from various file formats."""
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        try:
            if extension == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            elif extension == '.pdf':
                return self._extract_from_pdf(file_path)
            elif extension in ['.docx', '.doc']:
                return self._extract_from_docx(file_path)
            elif extension in ['.md', '.markdown']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            elif extension == '.html':
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Simple HTML tag removal
                    content = f.read()
                    return re.sub(r'<[^>]+>', '', content)
            else:
                logger.warning(f"Unsupported file format: {extension}")
                return ""
        except Exception as e:
            logger.error(f"Failed to extract text from {file_path}: {e}")
            return ""
    
    def _extract_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file."""
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            logger.error(f"Failed to extract from PDF {file_path}: {e}")
            return ""
    
    def _extract_from_docx(self, file_path: Path) -> str:
        """Extract text from DOCX file."""
        try:
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            logger.error(f"Failed to extract from DOCX {file_path}: {e}")
            return ""
    
    def _create_chunks(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create chunks from text."""
        # Simple chunking by sentences
        sentences = sent_tokenize(text)
        chunks = []
        current_chunk = ""
        current_size = 0
        max_chunk_size = 1000  # characters
        
        for sentence in sentences:
            if current_size + len(sentence) > max_chunk_size and current_chunk:
                chunks.append({
                    "content": current_chunk.strip(),
                    "metadata": metadata.copy(),
                    "chunk_index": len(chunks)
                })
                current_chunk = sentence
                current_size = len(sentence)
            else:
                current_chunk += " " + sentence
                current_size += len(sentence)
        
        # Add the last chunk
        if current_chunk.strip():
            chunks.append({
                "content": current_chunk.strip(),
                "metadata": metadata.copy(),
                "chunk_index": len(chunks)
            })
        
        return chunks
    
    def _generate_embeddings(self, text: str) -> List[float]:
        """Generate embeddings using Bedrock."""
        try:
            response = self.bedrock_client.invoke_model(
                modelId=self.config["bedrock"]["embeddingModelId"],
                body=json.dumps({
                    "inputText": text
                })
            )
            
            result = json.loads(response['body'].read())
            return result['embedding']
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            # Return zero vector as fallback
            return [0.0] * self.config["vectorIndex"]["dimensions"]
    
    def _store_vectors_to_s3(self, document_id: str, chunks: List[Dict], embeddings: List[List[float]]):
        """Store vectors and metadata to S3."""
        try:
            # Get bucket names from CloudFormation stack
            cf_client = boto3.client('cloudformation', region_name=self.region)
            response = cf_client.describe_stacks(StackName='ChatbotRagStack')
            
            outputs = {}
            for output in response['Stacks'][0].get('Outputs', []):
                outputs[output['OutputKey']] = output['OutputValue']
            
            vector_bucket = outputs.get('VectorBucketName')
            metadata_bucket = outputs.get('MetadataBucketName')
            
            if not vector_bucket or not metadata_bucket:
                raise ValueError(f"Could not find bucket names in stack outputs. Available outputs: {list(outputs.keys())}")
            
            logger.info(f"Using vector bucket: {vector_bucket}, metadata bucket: {metadata_bucket}")
            
            # Store vectors
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                vector_key = f"{document_id}/chunk_{i}.json"
                vector_data = {
                    "document_id": document_id,
                    "chunk_index": i,
                    "content": chunk["content"],
                    "embedding": embedding,
                    "metadata": chunk["metadata"]
                }
                
                self.s3_client.put_object(
                    Bucket=vector_bucket,
                    Key=vector_key,
                    Body=json.dumps(vector_data),
                    ContentType='application/json'
                )
            
            # Store document metadata
            metadata = {
                "document_id": document_id,
                "chunk_count": len(chunks),
                "processed_at": time.time(),
                "total_chunks": len(chunks)
            }
            
            self.s3_client.put_object(
                Bucket=metadata_bucket,
                Key=f"{document_id}.json",
                Body=json.dumps(metadata),
                ContentType='application/json'
            )
            
            logger.info(f"Stored {len(chunks)} chunks for document {document_id}")
            
        except Exception as e:
            logger.error(f"Failed to store vectors to S3: {e}")
            raise
    
    def process_file(self, file_path: str, document_id: str = None) -> Dict[str, Any]:
        """Process a single file."""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            if document_id is None:
                document_id = file_path.stem
            
            logger.info(f"Processing file: {file_path}")
            
            # Extract text from document
            logger.info("Extracting text...")
            text_content = self._extract_text_from_file(str(file_path))
            
            if not text_content.strip():
                logger.warning(f"No text content extracted from {file_path}")
                return {"status": "skipped", "reason": "No text content"}
            
            # Create chunks
            logger.info("Creating chunks...")
            chunks = self._create_chunks(text_content, {
                "title": file_path.name,
                "source": str(file_path),
                "document_id": document_id
            })
            
            logger.info(f"Created {len(chunks)} chunks")
            
            # Generate embeddings for all chunks
            logger.info("Generating embeddings...")
            embeddings = []
            for i, chunk in enumerate(chunks):
                try:
                    embedding = self._generate_embeddings(chunk["content"])
                    embeddings.append(embedding)
                    if (i + 1) % 10 == 0:
                        logger.info(f"Generated embeddings for {i + 1}/{len(chunks)} chunks")
                except Exception as e:
                    logger.error(f"Failed to generate embedding for chunk {i}: {e}")
                    # Use zero vector as fallback
                    embeddings.append([0.0] * self.config["vectorIndex"]["dimensions"])
            
            # Store vectors and metadata
            logger.info("Storing vectors and metadata...")
            self._store_vectors_to_s3(document_id, chunks, embeddings)
            
            logger.info(f"Successfully processed {file_path}")
            return {
                "status": "success",
                "document_id": document_id,
                "chunks_processed": len(chunks),
                "file_size": file_path.stat().st_size
            }
            
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def process_folder(self, folder_path: str, recursive: bool = True) -> Dict[str, Any]:
        """Process all documents in a folder."""
        folder_path = Path(folder_path)
        if not folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        # Supported file extensions
        supported_extensions = {'.pdf', '.docx', '.doc', '.txt', '.md', '.html', '.csv', '.json'}
        
        # Find all files
        if recursive:
            files = [f for f in folder_path.rglob('*') if f.suffix.lower() in supported_extensions]
        else:
            files = [f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() in supported_extensions]
        
        logger.info(f"Found {len(files)} files to process in {folder_path}")
        
        results = {
            "total_files": len(files),
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "details": []
        }
        
        for file_path in files:
            try:
                # Use relative path as document ID
                relative_path = file_path.relative_to(folder_path)
                document_id = str(relative_path).replace('/', '_').replace('\\', '_')
                
                result = self.process_file(file_path, document_id)
                results["details"].append({
                    "file": str(file_path),
                    "document_id": document_id,
                    "result": result
                })
                
                if result["status"] == "success":
                    results["processed"] += 1
                elif result["status"] == "skipped":
                    results["skipped"] += 1
                else:
                    results["errors"] += 1
                    
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                results["errors"] += 1
                results["details"].append({
                    "file": str(file_path),
                    "result": {"status": "error", "error": str(e)}
                })
        
        return results
    
    def delete_document(self, document_id: str) -> Dict[str, Any]:
        """Delete a document and its vectors."""
        try:
            # Get bucket names from CloudFormation stack
            cf_client = boto3.client('cloudformation', region_name=self.region)
            response = cf_client.describe_stacks(StackName='ChatbotRagStack')
            
            outputs = {}
            for output in response['Stacks'][0].get('Outputs', []):
                outputs[output['OutputKey']] = output['OutputValue']
            
            vector_bucket = outputs.get('VectorBucketName')
            metadata_bucket = outputs.get('MetadataBucketName')
            
            # Delete all chunks for this document
            paginator = self.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=vector_bucket, Prefix=f"{document_id}/"):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        self.s3_client.delete_object(Bucket=vector_bucket, Key=obj['Key'])
            
            # Delete metadata
            try:
                self.s3_client.delete_object(Bucket=metadata_bucket, Key=f"{document_id}.json")
            except:
                pass  # Metadata might not exist
            
            logger.info(f"Successfully deleted document: {document_id}")
            return {"status": "success", "document_id": document_id}
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return {"status": "error", "error": str(e)}

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Process documents locally and upload to S3")
    parser.add_argument("--file", help="Process a single file")
    parser.add_argument("--folder", help="Process all files in a folder")
    parser.add_argument("--recursive", action="store_true", help="Process folder recursively")
    parser.add_argument("--document-id", help="Document ID for single file processing")
    parser.add_argument("--delete", help="Delete a document by ID")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--batch", action="store_true", help="Enable batch processing mode")
    
    args = parser.parse_args()
    
    if not any([args.file, args.folder, args.delete]):
        parser.print_help()
        sys.exit(1)
    
    processor = LocalDocumentProcessor(args.config)
    
    try:
        if args.delete:
            result = processor.delete_document(args.delete)
            print(json.dumps(result, indent=2))
        elif args.file:
            result = processor.process_file(args.file, args.document_id)
            print(json.dumps(result, indent=2))
        elif args.folder:
            result = processor.process_folder(args.folder, args.recursive)
            print(json.dumps(result, indent=2))
            
            # Print summary
            print(f"\nProcessing Summary:")
            print(f"Total files: {result['total_files']}")
            print(f"Processed: {result['processed']}")
            print(f"Skipped: {result['skipped']}")
            print(f"Errors: {result['errors']}")
            
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
