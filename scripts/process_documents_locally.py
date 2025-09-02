#!/usr/bin/env python3
"""
Local document processing script with AWS token renewal support.
This script processes documents locally and uploads the results to S3.
Includes automatic AWS credential refresh to handle long-running operations.
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
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import multiprocessing as mp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import psutil, fallback to basic detection
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil not available, using basic resource detection")

# Import required libraries
import boto3
import numpy as np
from scipy.spatial.distance import cosine
import nltk
from nltk.tokenize import sent_tokenize
from botocore.exceptions import ClientError, TokenRetrievalError, NoCredentialsError

# Download NLTK data if needed - support both old and new versions
def ensure_nltk_resources():
    """Ensure required NLTK resources are available."""
    resources_needed = ['punkt_tab', 'punkt']  # Try new version first, fallback to old
    for resource in resources_needed:
        try:
            nltk.data.find(f'tokenizers/{resource}')
            logger.info(f"Found NLTK resource: {resource}")
            return  # Success, we have what we need
        except LookupError:
            try:
                logger.info(f"Downloading NLTK resource: {resource}")
                nltk.download(resource, quiet=True)
                return  # Successfully downloaded
            except Exception as e:
                logger.warning(f"Failed to download {resource}: {e}")
                continue  # Try next resource
    
    # If we get here, log an error
    logger.error("Could not download any NLTK punkt resources, processing will fail")

# Call the function
ensure_nltk_resources()

# Document processing imports
try:
    import PyPDF2
    from docx import Document
    from PIL import Image
    import textstat
except ImportError as e:
    logger.warning(f"Some document processing libraries not available: {e}")


def _process_single_file_cpu_task(file_path_str: str) -> Dict[str, Any]:
    """CPU-intensive processing for a single file - module level for pickling."""
    try:
        from pathlib import Path
        import nltk
        from nltk.tokenize import sent_tokenize
        
        file_path = Path(file_path_str)
        
        # Extract text using basic extraction
        def extract_text_basic(file_path: Path) -> str:
            extension = file_path.suffix.lower()
            if extension == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            elif extension in ['.md', '.markdown']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                return ""
        
        # Create chunks using basic chunking
        def create_chunks_basic(text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
            sentences = sent_tokenize(text)
            chunks = []
            max_chunk_size = 750
            overlap_size = 100
            
            current_chunk = ""
            current_size = 0
            
            for sentence in sentences:
                if current_size + len(sentence) > max_chunk_size and current_chunk:
                    chunks.append({
                        "content": current_chunk.strip(),
                        "metadata": metadata.copy(),
                        "chunk_index": len(chunks)
                    })
                    
                    # Start new chunk with overlap
                    overlap_text = current_chunk[-overlap_size:] if len(current_chunk) > overlap_size else current_chunk
                    current_chunk = overlap_text + " " + sentence
                    current_size = len(current_chunk)
                else:
                    if current_chunk:
                        current_chunk += " " + sentence
                    else:
                        current_chunk = sentence
                    current_size += len(sentence)
            
            if current_chunk.strip():
                chunks.append({
                    "content": current_chunk.strip(),
                    "metadata": metadata.copy(),
                    "chunk_index": len(chunks)
                })
            
            return chunks
        
        text_content = extract_text_basic(file_path)
        if not text_content.strip():
            return {"file_path": file_path_str, "status": "empty", "chunks": []}
        
        chunks = create_chunks_basic(text_content, {
            "title": file_path.name,
            "source": str(file_path),
            "document_id": file_path.stem
        })
        
        return {
            "file_path": file_path_str,
            "status": "success", 
            "chunks": chunks,
            "text_length": len(text_content)
        }
    except Exception as e:
        return {"file_path": file_path_str, "status": "error", "error": str(e)}


class AWSClientManager:
    """Manages AWS clients with automatic credential refresh."""
    
    def __init__(self, region: str):
        self.region = region
        self._clients = {}
        self._client_creation_time = {}
        self._refresh_threshold = timedelta(minutes=15)  # Refresh every 15 minutes to be very safe
        
    def _should_refresh_client(self, service_name: str) -> bool:
        """Check if client should be refreshed based on age."""
        if service_name not in self._client_creation_time:
            return True
        
        age = datetime.now() - self._client_creation_time[service_name]
        return age > self._refresh_threshold
    
    def _create_client(self, service_name: str):
        """Create a new AWS client with fresh credentials."""
        try:
            # Force new session to get fresh credentials
            session = boto3.Session()
            client = session.client(service_name, region_name=self.region)
            self._clients[service_name] = client
            self._client_creation_time[service_name] = datetime.now()
            logger.info(f"Created new {service_name} client with fresh credentials")
            return client
        except Exception as e:
            logger.error(f"Failed to create {service_name} client: {e}")
            raise
    
    def get_client(self, service_name: str):
        """Get AWS client, refreshing if necessary."""
        if (service_name not in self._clients or 
            self._should_refresh_client(service_name)):
            return self._create_client(service_name)
        
        return self._clients[service_name]
    
    def refresh_all_clients(self):
        """Force refresh of all clients."""
        logger.info("Refreshing all AWS clients with fresh credentials...")
        for service_name in list(self._clients.keys()):
            self._create_client(service_name)


class LocalDocumentProcessor:
    """Local document processor with full functionality."""
    
    def __init__(self, config_path: str = None):
        """Initialize the processor."""
        self.config = self._load_config(config_path)
        self.region = self._get_aws_region()
        self.aws_manager = AWSClientManager(self.region)
        
        # Test initial connection
        self._test_aws_connection()
        
    def _test_aws_connection(self):
        """Test AWS connection and credentials."""
        try:
            sts_client = self.aws_manager.get_client('sts')
            identity = sts_client.get_caller_identity()
            logger.info(f"AWS connection successful. Account: {identity.get('Account')}, User: {identity.get('Arn')}")
        except Exception as e:
            logger.error(f"AWS connection failed: {e}")
            raise
    
    def _get_bedrock_client(self):
        """Get Bedrock client with automatic refresh."""
        return self.aws_manager.get_client('bedrock-runtime')
    
    def _get_s3_client(self):
        """Get S3 client with automatic refresh."""
        return self.aws_manager.get_client('s3')
    
    def _get_cloudformation_client(self):
        """Get CloudFormation client with automatic refresh."""
        return self.aws_manager.get_client('cloudformation')
    
    def _retry_with_refresh(self, func, *args, max_retries=3, **kwargs):
        """Execute function with automatic client refresh on token expiry."""
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                error_message = str(e)
                
                # Check for various token expiration error patterns
                is_token_error = (
                    error_code in [
                        'ExpiredToken', 'TokenRefreshRequired', 'InvalidToken', 
                        'UnauthorizedOperation', 'ExpiredTokenException',  # ← Added Bedrock-specific error
                        'InvalidTokenException', 'TokenExpiredException'
                    ] or
                    'expired' in error_message.lower() or
                    'token' in error_message.lower() or
                    'unauthorized' in error_message.lower()
                )
                
                if is_token_error and attempt < max_retries - 1:
                    logger.warning(f"Token expired (attempt {attempt + 1}/{max_retries}), refreshing clients...")
                    logger.warning(f"Error details: {error_code} - {error_message}")
                    self.aws_manager.refresh_all_clients()
                    time.sleep(2)  # Longer pause to ensure fresh credentials
                    continue
                raise
            except (TokenRetrievalError, NoCredentialsError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Credential error (attempt {attempt + 1}/{max_retries}), refreshing clients...")
                    self.aws_manager.refresh_all_clients()
                    time.sleep(2)
                    continue
                raise
            except Exception as e:
                # For other exceptions, check if it might be credential-related
                error_message = str(e).lower()
                if ('credential' in error_message or 'unauthorized' in error_message or 'expired' in error_message) and attempt < max_retries - 1:
                    logger.warning(f"Possible credential error (attempt {attempt + 1}/{max_retries}), refreshing clients...")
                    logger.warning(f"Error details: {str(e)}")
                    self.aws_manager.refresh_all_clients()
                    time.sleep(2)
                    continue
                raise
        
        raise Exception(f"Failed after {max_retries} attempts")
        
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
        """Get AWS region with comprehensive fallback chain."""
        # Try environment variables first
        region = (
            os.environ.get('AWS_REGION') or 
            os.environ.get('AWS_DEFAULT_REGION') or 
            os.environ.get('CDK_DEPLOY_REGION')
        )
        
        if region:
            return region
        
        # Try AWS CLI configuration
        try:
            import subprocess
            result = subprocess.run(['aws', 'configure', 'get', 'region'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, ImportError):
            pass
        
        # Try config.json if it exists
        try:
            config_path = Path(__file__).parent.parent / "config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    if config.get('region'):
                        return config['region']
        except (json.JSONDecodeError, IOError):
            pass
        
        # Final fallback with warning
        logger.warning("No region specified, defaulting to us-east-1")
        logger.warning("Set AWS_REGION environment variable or run 'aws configure' to specify region")
        return 'us-east-1'
    
    def _extract_text_streaming(self, file_path: str, chunk_size: int = 1024*1024) -> str:
        """Extract text from file using streaming for memory efficiency."""
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        # For large text files, use streaming
        if extension in ['.txt', '.md', '.markdown', '.html'] and file_path.stat().st_size > chunk_size:
            logger.info(f"Using streaming extraction for large file: {file_path}")
            content_parts = []
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        content_parts.append(chunk)
                return ''.join(content_parts)
            except Exception as e:
                logger.error(f"Streaming extraction failed for {file_path}: {e}")
                return ""
        
        # Fall back to regular extraction for other files or smaller files
        return self._extract_text_from_file(file_path)

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
        """Extract text from PDF file with multiple fallback methods."""
        # Method 1: Try standard PyPDF2
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            logger.warning(f"Standard PyPDF2 failed for {file_path}: {e}, trying alternative methods")
        
        # Method 2: Try PyPDF2 with strict=False
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f, strict=False)
                text = ""
                for page in reader.pages:
                    try:
                        text += page.extract_text() + "\n"
                    except Exception as page_error:
                        logger.warning(f"Failed to extract page from {file_path}: {page_error}")
                        continue
                if text.strip():  # If we got some text, return it
                    return text
        except Exception as e:
            logger.warning(f"Alternative PyPDF2 method failed for {file_path}: {e}")
        
        # Method 3: Final fallback - return empty but log the failure
        logger.error(f"All PDF extraction methods failed for {file_path}, skipping file")
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
        """Create overlapping chunks from text with semantic metadata."""
        sentences = sent_tokenize(text)
        chunks = []
        
        # Adaptive chunking based on document size
        text_length = len(text)
        if text_length > 500000:  # Very large documents (>500KB)
            max_chunk_size = 600   # Smaller chunks for large docs
            overlap_size = 75      # Reduced overlap
            logger.info(f"Using small chunks for large document ({text_length:,} chars)")
        elif text_length > 100000:  # Large documents (>100KB)
            max_chunk_size = 700   # Medium chunks
            overlap_size = 90      # Medium overlap
            logger.info(f"Using medium chunks for large document ({text_length:,} chars)")
        else:  # Normal documents
            max_chunk_size = 750   # Standard chunks
            overlap_size = 100     # Standard overlap
        
        current_chunk = ""
        current_size = 0
        sentence_buffer = []  # Keep track of sentences for overlap
        
        for i, sentence in enumerate(sentences):
            sentence_buffer.append(sentence)
            
            if current_size + len(sentence) > max_chunk_size and current_chunk:
                # Extract metadata for this chunk
                chunk_metadata = self._extract_chunk_metadata(current_chunk, len(chunks), metadata)
                
                # Create current chunk with metadata
                chunks.append({
                    "content": current_chunk.strip(),
                    "metadata": metadata.copy(),
                    "chunk_index": len(chunks),
                    "heading": chunk_metadata["heading"],
                    "chunk_type": chunk_metadata["chunk_type"],
                    "key_entities": chunk_metadata["key_entities"],
                    "topics": chunk_metadata["topics"],
                    "importance_score": chunk_metadata["importance_score"],
                    "context_summary": chunk_metadata["context_summary"]
                })
                
                # Calculate overlap for next chunk
                overlap_text = ""
                overlap_length = 0
                
                # Work backwards through sentence buffer to create overlap
                for j in range(len(sentence_buffer) - 1, -1, -1):
                    sentence_len = len(sentence_buffer[j])
                    if overlap_length + sentence_len <= overlap_size:
                        overlap_text = sentence_buffer[j] + " " + overlap_text
                        overlap_length += sentence_len
                    else:
                        break
                
                # Start new chunk with overlap + current sentence
                current_chunk = overlap_text.strip()
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                current_size = len(current_chunk)
                
                # Reset sentence buffer, keeping only sentences in overlap
                overlap_sentences = []
                temp_length = 0
                for j in range(len(sentence_buffer) - 1, -1, -1):
                    if temp_length + len(sentence_buffer[j]) <= overlap_size:
                        overlap_sentences.insert(0, sentence_buffer[j])
                        temp_length += len(sentence_buffer[j])
                    else:
                        break
                overlap_sentences.append(sentence)
                sentence_buffer = overlap_sentences
                
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                current_size += len(sentence)
        
        # Add the last chunk with metadata
        if current_chunk.strip():
            chunk_metadata = self._extract_chunk_metadata(current_chunk, len(chunks), metadata)
            chunks.append({
                "content": current_chunk.strip(),
                "metadata": metadata.copy(),
                "chunk_index": len(chunks),
                "heading": chunk_metadata["heading"],
                "chunk_type": chunk_metadata["chunk_type"],
                "key_entities": chunk_metadata["key_entities"],
                "topics": chunk_metadata["topics"],
                "importance_score": chunk_metadata["importance_score"],
                "context_summary": chunk_metadata["context_summary"]
            })
        
        # Add relationship context between chunks
        self._add_chunk_relationships(chunks)
        
        return chunks
    
    def _extract_chunk_metadata(self, chunk_text: str, chunk_index: int, doc_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract semantic metadata from chunk content."""
        try:
            # Extract heading (look for title-like patterns)
            heading = self._extract_heading(chunk_text)
            
            # Determine chunk type based on content patterns
            chunk_type = self._classify_chunk_type(chunk_text)
            
            # Extract key entities (names, places, important terms)
            key_entities = self._extract_key_entities(chunk_text)
            
            # Extract topics/themes
            topics = self._extract_topics(chunk_text)
            
            # Calculate importance score
            importance_score = self._calculate_importance_score(chunk_text, chunk_type, key_entities)
            
            # Create context summary
            context_summary = self._create_context_summary(chunk_text, heading, chunk_type)
            
            return {
                "heading": heading,
                "chunk_type": chunk_type,
                "key_entities": key_entities,
                "topics": topics,
                "importance_score": importance_score,
                "context_summary": context_summary
            }
        except Exception as e:
            logger.warning(f"Failed to extract chunk metadata: {e}")
            return {
                "heading": "",
                "chunk_type": "paragraph",
                "key_entities": [],
                "topics": [],
                "importance_score": 1.0,
                "context_summary": chunk_text[:100] + "..."
            }
    
    def _extract_heading(self, text: str) -> str:
        """Extract heading or title from chunk text."""
        lines = text.strip().split('\n')
        first_line = lines[0].strip()
        
        # Check for common heading patterns
        if (len(first_line) < 100 and 
            (first_line.isupper() or 
             first_line.istitle() or
             any(marker in first_line.lower() for marker in ['chapter', 'section', 'part']))):
            return first_line
        
        # Look for sentences that might be titles
        sentences = sent_tokenize(text)
        if sentences:
            first_sentence = sentences[0].strip()
            if len(first_sentence) < 80 and first_sentence.endswith('.'):
                return first_sentence[:-1]  # Remove trailing period
        
        return ""
    
    def _classify_chunk_type(self, text: str) -> str:
        """Classify the type of content in the chunk."""
        text_lower = text.lower()
        
        # Dialogue detection
        if '"' in text and text.count('"') >= 2:
            return "dialogue"
        
        # Narrative patterns
        if any(pattern in text_lower for pattern in ['once upon', 'long ago', 'in the beginning']):
            return "narrative_opening"
        
        # Action/event description
        if any(pattern in text_lower for pattern in ['suddenly', 'then', 'meanwhile', 'after']):
            return "action"
        
        # Character description
        if any(pattern in text_lower for pattern in ['he was', 'she was', 'they were', 'appeared to be']):
            return "description"
        
        # Question or problem
        if '?' in text or any(pattern in text_lower for pattern in ['how', 'what', 'why', 'problem']):
            return "question"
        
        return "paragraph"
    
    def _extract_key_entities(self, text: str) -> List[str]:
        """Extract key entities like names, places, important terms."""
        entities = []
        
        # Simple pattern-based entity extraction
        import re
        
        # Proper nouns (capitalized words)
        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        entities.extend(proper_nouns[:5])  # Limit to top 5
        
        # Quoted terms (often important)
        quoted_terms = re.findall(r'"([^"]+)"', text)
        entities.extend(quoted_terms[:3])
        
        # Remove duplicates and common words
        common_words = {'The', 'This', 'That', 'Then', 'When', 'Where', 'What', 'How', 'Why'}
        entities = [e for e in set(entities) if e not in common_words and len(e) > 2]
        
        return entities[:8]  # Return top 8 entities
    
    def _extract_topics(self, text: str) -> List[str]:
        """Extract main topics/themes from the text."""
        topics = []
        text_lower = text.lower()
        
        # Topic keywords mapping
        topic_keywords = {
            'magic': ['magic', 'spell', 'enchant', 'wizard', 'fairy', 'potion'],
            'adventure': ['journey', 'quest', 'travel', 'explore', 'adventure'],
            'romance': ['love', 'heart', 'marry', 'wedding', 'kiss'],
            'conflict': ['fight', 'battle', 'war', 'enemy', 'defeat'],
            'mystery': ['secret', 'hidden', 'mystery', 'unknown', 'discover'],
            'family': ['father', 'mother', 'son', 'daughter', 'family'],
            'nature': ['forest', 'sea', 'mountain', 'river', 'tree'],
            'royalty': ['king', 'queen', 'prince', 'princess', 'castle']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic)
        
        return topics[:4]  # Return top 4 topics
    
    def _calculate_importance_score(self, text: str, chunk_type: str, entities: List[str]) -> float:
        """Calculate importance score for ranking."""
        score = 1.0
        
        # Boost based on chunk type
        type_weights = {
            'dialogue': 1.3,
            'narrative_opening': 1.4,
            'question': 1.2,
            'action': 1.1,
            'description': 0.9,
            'paragraph': 1.0
        }
        score *= type_weights.get(chunk_type, 1.0)
        
        # Boost based on entities
        score += len(entities) * 0.1
        
        # Boost for questions and exclamations
        score += text.count('?') * 0.1
        score += text.count('!') * 0.05
        
        # Boost for dialogue
        score += text.count('"') * 0.05
        
        return min(score, 2.0)  # Cap at 2.0
    
    def _create_context_summary(self, text: str, heading: str, chunk_type: str) -> str:
        """Create a brief context summary for the chunk."""
        if heading:
            return f"{chunk_type.title()}: {heading}"
        
        # Create summary from first sentence
        sentences = sent_tokenize(text)
        if sentences:
            first_sentence = sentences[0][:100]
            return f"{chunk_type.title()}: {first_sentence}..."
        
        return f"{chunk_type.title()}: {text[:80]}..."
    
    def _add_chunk_relationships(self, chunks: List[Dict[str, Any]]) -> None:
        """Add relationship context between chunks."""
        for i, chunk in enumerate(chunks):
            # Add previous chunk context
            if i > 0:
                prev_chunk = chunks[i-1]
                chunk["prev_context"] = {
                    "heading": prev_chunk.get("heading", ""),
                    "chunk_type": prev_chunk.get("chunk_type", ""),
                    "summary": prev_chunk.get("context_summary", "")[:50]
                }
            
            # Add next chunk context (will be filled for previous chunks)
            if i < len(chunks) - 1:
                next_chunk = chunks[i+1]
                chunk["next_context"] = {
                    "heading": next_chunk.get("heading", ""),
                    "chunk_type": next_chunk.get("chunk_type", ""),
                    "summary": next_chunk.get("context_summary", "")[:50]
                }
            
            # Add position context
            chunk["position_context"] = {
                "chunk_position": i + 1,
                "total_chunks": len(chunks),
                "relative_position": (i + 1) / len(chunks)  # 0.0 to 1.0
            }
    
    def _process_cpu_tasks_parallel(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Parallel text extraction and chunking using process pool.
        
        Args:
            file_paths: List of file paths to process
            
        Returns:
            List of processing results with status, chunks, and metadata
            
        Note:
            Uses ProcessPoolExecutor for CPU-intensive tasks (text extraction, chunking).
            Conservative worker limit prevents system overload.
        """
        if not file_paths:
            logger.warning("No file paths provided for CPU parallelization")
            return []
            
        logger.info(f"Starting CPU parallelization for {len(file_paths)} files")
        
        # Calculate optimal worker count
        max_workers = min(mp.cpu_count(), len(file_paths), 4)
        logger.info(f"Using {max_workers} CPU workers for parallel processing")
        
        results = []
        try:
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                future_to_path = {executor.submit(_process_single_file_cpu_task, path): path for path in file_paths}
                
                for future in as_completed(future_to_path):
                    try:
                        result = future.result(timeout=900)
                        results.append(result)
                        
                        # Progress logging
                        if len(results) % 5 == 0 or len(results) == len(file_paths):
                            logger.info(f"CPU processing progress: {len(results)}/{len(file_paths)} files completed")
                            
                    except Exception as e:
                        path = future_to_path[future]
                        logger.error(f"Future execution failed for {path}: {e}")
                        results.append({"file_path": path, "status": "error", "error": str(e)})
                        
        except Exception as e:
            logger.error(f"ProcessPoolExecutor failed: {e}")
            # Fallback to sequential processing
            logger.info("Falling back to sequential CPU processing")
            for path in file_paths:
                results.append(_process_single_file_cpu_task(path))
        
        successful = sum(1 for r in results if r["status"] == "success")
        logger.info(f"CPU parallelization completed: {successful}/{len(file_paths)} files successful")
        return results

    def _get_optimal_batch_config(self) -> Dict[str, int]:
        """
        Calculate optimal batch sizes based on system resources.
        
        Returns:
            Dictionary with optimal batch sizes and worker counts
            
        Note:
            Uses psutil when available for accurate memory detection.
            Falls back to CPU-based estimation for compatibility.
        """
        cpu_count = mp.cpu_count()
        
        # Get memory info with fallback
        if HAS_PSUTIL:
            try:
                memory_gb = psutil.virtual_memory().total / (1024**3)
                logger.debug("Using psutil for accurate memory detection")
            except Exception as e:
                logger.warning(f"psutil memory detection failed: {e}, using fallback")
                memory_gb = max(2.0, cpu_count * 0.5)
        else:
            # Fallback: assume reasonable memory based on CPU count
            memory_gb = max(2.0, cpu_count * 0.5)
            logger.debug("Using CPU-based memory estimation")
        
        # Dynamic batch sizing with conservative limits
        embedding_batch_size = min(50, max(10, cpu_count * 8))
        embedding_workers = min(4, max(2, cpu_count // 2))
        document_workers = min(3, max(1, cpu_count // 3))
        
        logger.info(f"System resources: {cpu_count} CPUs, {memory_gb:.1f}GB RAM")
        logger.info(f"Optimal configuration: embed_batch={embedding_batch_size}, embed_workers={embedding_workers}, doc_workers={document_workers}")
        
        return {
            "embedding_batch_size": embedding_batch_size,
            "embedding_workers": embedding_workers,
            "document_workers": document_workers
        }

    def _process_embeddings_intelligent_batches(self, chunks: List[str]) -> List[List[float]]:
        """
        Process embeddings with intelligent batching based on system resources.
        
        Args:
            chunks: List of text chunks to generate embeddings for
            
        Returns:
            List of embedding vectors
            
        Note:
            Automatically determines optimal batch sizes and worker counts.
            Provides progress logging for long-running operations.
        """
        if not chunks:
            logger.warning("No chunks provided for embedding generation")
            return []
            
        try:
            config = self._get_optimal_batch_config()
            batch_size = config["embedding_batch_size"]
            workers = config["embedding_workers"]
            
            logger.info(f"Processing {len(chunks)} embeddings in batches of {batch_size} with {workers} workers")
            
            all_embeddings = []
            total_batches = (len(chunks) + batch_size - 1) // batch_size
            
            for i in range(0, len(chunks), batch_size):
                batch_num = i // batch_size + 1
                batch = chunks[i:i + batch_size]
                
                try:
                    batch_embeddings = self._generate_embeddings_parallel(batch, max_workers=workers)
                    all_embeddings.extend(batch_embeddings)
                    
                    logger.info(f"Completed embedding batch {batch_num}/{total_batches} ({len(batch)} chunks)")
                    
                    # Add delay between batches to prevent throttling
                    if batch_num < total_batches:  # Don't delay after the last batch
                        time.sleep(3)  # 3 second delay between batches
                    
                except Exception as e:
                    logger.error(f"Batch {batch_num} failed: {e}")
                    # Add zero vectors as fallback
                    fallback_embeddings = [[0.0] * self.config["vectorIndex"]["dimensions"]] * len(batch)
                    all_embeddings.extend(fallback_embeddings)
            
            logger.info(f"Intelligent batching completed: {len(all_embeddings)} embeddings generated")
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Intelligent batching failed: {e}")
            # Fallback to sequential processing
            logger.info("Falling back to sequential embedding generation")
            return [self._generate_embeddings(chunk) for chunk in chunks]

    def _generate_embeddings_parallel(self, chunks: List[str], max_workers: int = 3) -> List[List[float]]:
        """Generate embeddings in parallel with controlled concurrency and throttle protection."""
        logger.info(f"Generating embeddings for {len(chunks)} chunks using {max_workers} workers")
        
        def generate_single_embedding(chunk_text: str) -> List[float]:
            # Add delay between individual embedding calls to prevent throttling
            time.sleep(1)  # 1 second delay between chunks
            return self._generate_embeddings(chunk_text)
        
        embeddings = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(generate_single_embedding, chunk): i 
                for i, chunk in enumerate(chunks)
            }
            
            # Collect results in order
            results = [None] * len(chunks)
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    logger.error(f"Failed to generate embedding for chunk {index}: {e}")
                    results[index] = [0.0] * self.config["vectorIndex"]["dimensions"]
                
                # Progress logging
                completed = sum(1 for r in results if r is not None)
                if completed % 5 == 0 or completed == len(chunks):
                    logger.info(f"Generated embeddings: {completed}/{len(chunks)}")
        
        return results

    def _generate_embeddings(self, text: str) -> List[float]:
        """Generate embeddings using Bedrock with text length validation."""
        def _generate():
            bedrock_client = self._get_bedrock_client()
            
            # Process text length for better embedding quality
            processed_text = self._optimize_text_for_embedding(text)
            
            # Skip empty or whitespace-only text
            if not processed_text.strip():
                logger.warning("Empty text provided for embedding generation")
                return [0.001] * self.config["vectorIndex"]["dimensions"]  # Small non-zero vector
            
            response = bedrock_client.invoke_model(
                modelId=self.config["bedrock"]["embeddingModelId"],
                body=json.dumps({
                    "inputText": processed_text
                })
            )
            
            result = json.loads(response['body'].read())
            embedding = result['embedding']
            
            # Validate embedding to prevent zero norm vectors
            if not self._validate_embedding(embedding):
                logger.warning(f"Invalid embedding generated for text: {processed_text[:100]}...")
                return self._generate_fallback_embedding(processed_text)
            
            return embedding
        
        try:
            return self._retry_with_refresh(_generate)
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            # Return small non-zero vector as fallback
            return [0.001] * self.config["vectorIndex"]["dimensions"]
    
    def _validate_embedding(self, embedding: List[float]) -> bool:
        """Validate that embedding is not zero norm and contains valid values."""
        try:
            if not embedding or len(embedding) != self.config["vectorIndex"]["dimensions"]:
                return False
            
            # Check for all zeros or invalid values
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
    
    def _generate_fallback_embedding(self, text: str) -> List[float]:
        """Generate a deterministic fallback embedding for problematic text."""
        try:
            import hashlib
            
            # Create a deterministic hash-based embedding
            text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
            
            # Convert hash to embedding vector
            embedding = []
            dimensions = self.config["vectorIndex"]["dimensions"]
            
            for i in range(dimensions):
                # Use different parts of the hash to create variation
                hash_part = text_hash[(i * 2) % len(text_hash):(i * 2 + 2) % len(text_hash)]
                if len(hash_part) < 2:
                    hash_part = text_hash[:2]
                
                # Convert to float in range [-0.1, 0.1] to ensure small but non-zero values
                value = (int(hash_part, 16) / 255.0 - 0.5) * 0.2
                embedding.append(value)
            
            # Ensure the vector has a small but non-zero norm
            norm_squared = sum(x * x for x in embedding)
            if norm_squared == 0.0:
                embedding[0] = 0.001  # Ensure non-zero norm
            
            logger.info(f"Generated fallback embedding for problematic text")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate fallback embedding: {e}")
            # Final fallback: small random-like vector
            return [0.001 * (i % 3 - 1) for i in range(self.config["vectorIndex"]["dimensions"])]
    
    def _optimize_text_for_embedding(self, text: str) -> str:
        """Optimize text length and content for embedding generation."""
        optimal_length = 3000  # Optimized: reduced from 8000
        
        if len(text) <= optimal_length:
            return text
        
        # Intelligent truncation - keep most important parts
        sentences = sent_tokenize(text)
        
        # Strategy 1: Keep beginning and end (preserves context)
        if len(sentences) > 4:
            keep_start = len(sentences) // 3
            keep_end = len(sentences) // 3
            selected_sentences = sentences[:keep_start] + sentences[-keep_end:]
            truncated = " ".join(selected_sentences)
            
            if len(truncated) <= optimal_length:
                return truncated
        
        # Strategy 2: Simple truncation with sentence boundary
        truncated = text[:optimal_length]
        last_sentence_end = max(
            truncated.rfind('.'),
            truncated.rfind('!'),
            truncated.rfind('?')
        )
        
        if last_sentence_end > optimal_length * 0.8:  # If we can keep 80% and end on sentence
            return truncated[:last_sentence_end + 1]
        
        return truncated
    
    def _get_bucket_names(self):
        """Get bucket names from CloudFormation with retry logic."""
        def _get_buckets():
            cf_client = self._get_cloudformation_client()
            response = cf_client.describe_stacks(StackName='ChatbotRagStack')
            
            outputs = {}
            for output in response['Stacks'][0].get('Outputs', []):
                outputs[output['OutputKey']] = output['OutputValue']
            
            vector_bucket = outputs.get('VectorBucketName')
            metadata_bucket = outputs.get('MetadataBucketName')
            
            if not vector_bucket or not metadata_bucket:
                raise ValueError(f"Could not find bucket names in stack outputs. Available outputs: {list(outputs.keys())}")
            
            return vector_bucket, metadata_bucket
        
        return self._retry_with_refresh(_get_buckets)
    
    def _store_vectors_to_s3(self, document_id: str, chunks: List[Dict], embeddings: List[List[float]]):
        """Store vectors and metadata using S3 Vector buckets."""
        logger.info("Storing vectors and metadata...")
        
        # Get bucket names with retry logic
        vector_bucket, metadata_bucket = self._get_bucket_names()
        logger.info(f"Using vector bucket: {vector_bucket}, metadata bucket: {metadata_bucket}")
        
        # Prepare chunks with embeddings for S3 Vector API
        chunks_with_embeddings = []
        for chunk, embedding in zip(chunks, embeddings):
            chunk_with_embedding = chunk.copy()
            chunk_with_embedding["embedding"] = embedding
            chunks_with_embeddings.append(chunk_with_embedding)
        
        # Set environment variables for S3 Vector utils
        os.environ["VECTOR_BUCKET_NAME"] = vector_bucket
        os.environ["VECTOR_INDEX_NAME"] = self.config["vectorIndex"]["name"]
        
        # Import S3 Vector utilities
        try:
            # Add the src/backend directory to Python path
            import sys
            backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'backend')
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)
            
            from s3_vector_utils import store_document_vectors, store_document_metadata
            
            # Store vectors using S3 Vector API
            success = store_document_vectors(document_id, chunks_with_embeddings)
            if not success:
                raise Exception("Failed to store vectors using S3 Vector API")
            
            # Store document metadata in regular S3 bucket
            document_metadata = {
                "document_id": document_id,
                "total_chunks": len(chunks),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "vector_dimensions": len(embeddings[0]) if embeddings else 0,
                "content_summary": chunks[0]["content"][:200] + "..." if chunks else ""
            }
            
            # Store metadata in S3 bucket
            def _store_metadata():
                s3_client = self._get_s3_client()
                s3_client.put_object(
                    Bucket=metadata_bucket,
                    Key=f"{document_id}.json",
                    Body=json.dumps(document_metadata),
                    ContentType='application/json'
                )
            
            self._retry_with_refresh(_store_metadata)
            logger.info(f"Successfully stored {len(chunks)} vectors and metadata for document {document_id}")
            
        except ImportError as e:
            logger.error(f"S3 Vector utilities not available ({e})")
            raise Exception("S3 Vector utilities required but not available")
        except Exception as e:
            logger.error(f"Failed to store vectors: {e}")
            raise
            logger.info(f"Stored batch {batch_start + 1}-{batch_end} of {total_chunks} chunks")
        
        # Store document metadata with retry logic
        def _store_metadata():
            metadata = {
                "document_id": document_id,
                "chunk_count": len(chunks),
                "processed_at": time.time(),
                "total_chunks": len(chunks)
            }
            
            s3_client = self._get_s3_client()
            s3_client.put_object(
                Bucket=metadata_bucket,
                Key=f"{document_id}.json",
                Body=json.dumps(metadata),
                ContentType='application/json'
            )
        
        self._retry_with_refresh(_store_metadata)
        logger.info(f"Stored {len(chunks)} chunks for document {document_id}")
    
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
            text_content = self._extract_text_streaming(str(file_path))
            
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
            
            # Generate embeddings in parallel
            logger.info("Generating embeddings in parallel...")
            chunk_texts = [chunk["content"] for chunk in chunks]
            
            # Use parallel processing for embedding generation
            embeddings = self._generate_embeddings_parallel(chunk_texts, max_workers=3)
            
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
    
    def process_folder_advanced_parallel(self, folder_path: str, recursive: bool = True) -> Dict[str, Any]:
        """
        Advanced parallel processing with CPU task parallelization and intelligent batching.
        
        Args:
            folder_path: Path to folder containing documents
            recursive: Whether to process subdirectories
            
        Returns:
            Processing results with detailed statistics
            
        Note:
            Two-phase processing: CPU tasks (extraction/chunking) then embeddings.
            Provides maximum performance through intelligent resource utilization.
        """
        folder_path = Path(folder_path)
        if not folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        # Find all supported files
        supported_extensions = {'.pdf', '.docx', '.doc', '.txt', '.md', '.html', '.csv', '.json'}
        try:
            if recursive:
                files = [f for f in folder_path.rglob('*') if f.suffix.lower() in supported_extensions]
            else:
                files = [f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() in supported_extensions]
        except Exception as e:
            logger.error(f"Failed to scan folder {folder_path}: {e}")
            raise
        
        if not files:
            logger.warning(f"No supported files found in {folder_path}")
            return {"total_files": 0, "processed": 0, "skipped": 0, "errors": 0, "details": []}
        
        logger.info(f"Starting advanced parallel processing for {len(files)} files")
        
        try:
            config = self._get_optimal_batch_config()
            logger.info(f"Using advanced processing with system configuration")
        except Exception as e:
            logger.error(f"Failed to get optimal configuration: {e}")
            raise
        
        results = {"total_files": len(files), "processed": 0, "skipped": 0, "errors": 0, "details": []}
        
        try:
            # Phase 1: CPU-intensive tasks (text extraction + chunking) in parallel
            logger.info("Phase 1: Starting parallel CPU tasks (extraction + chunking)")
            file_paths = [str(f) for f in files]
            cpu_results = self._process_cpu_tasks_parallel(file_paths)
            
            # Phase 2: Process embeddings and storage for successful extractions
            logger.info("Phase 2: Starting embedding generation and storage")
            successful_cpu_results = [r for r in cpu_results if r["status"] == "success"]
            
            if successful_cpu_results:
                logger.info(f"Processing embeddings for {len(successful_cpu_results)} successfully extracted files")
            
            for cpu_result in cpu_results:
                file_path = Path(cpu_result["file_path"])
                try:
                    relative_path = file_path.relative_to(folder_path)
                    document_id = str(relative_path).replace('/', '_').replace('\\', '_')
                    
                    if cpu_result["status"] == "success":
                        try:
                            chunks = cpu_result["chunks"]
                            if not chunks:
                                logger.info(f"No chunks created for {file_path}")
                                results["skipped"] += 1
                                results["details"].append({
                                    "file": str(file_path),
                                    "document_id": document_id,
                                    "result": {"status": "skipped", "reason": "No chunks created"}
                                })
                                continue
                            
                            chunk_texts = [chunk["content"] for chunk in chunks]
                            
                            # Use intelligent batching for embeddings
                            embeddings = self._process_embeddings_intelligent_batches(chunk_texts)
                            
                            # Store results
                            self._store_vectors_to_s3(document_id, chunks, embeddings)
                            
                            results["processed"] += 1
                            results["details"].append({
                                "file": str(file_path),
                                "document_id": document_id,
                                "result": {
                                    "status": "success", 
                                    "chunks_processed": len(chunks),
                                    "text_length": cpu_result.get("text_length", 0)
                                }
                            })
                            
                            logger.info(f"Successfully processed {file_path} ({len(chunks)} chunks)")
                            
                        except Exception as e:
                            logger.error(f"Phase 2 processing failed for {file_path}: {e}")
                            results["errors"] += 1
                            results["details"].append({
                                "file": str(file_path),
                                "document_id": document_id,
                                "result": {"status": "error", "error": f"Phase 2 failed: {str(e)}"}
                            })
                    else:
                        # Handle CPU processing failures
                        if cpu_result["status"] == "empty":
                            results["skipped"] += 1
                            logger.info(f"Skipped {file_path} (no content)")
                        else:
                            results["errors"] += 1
                            logger.error(f"CPU processing failed for {file_path}: {cpu_result.get('error', 'Unknown error')}")
                        
                        results["details"].append({
                            "file": str(file_path),
                            "result": {
                                "status": cpu_result["status"], 
                                "error": cpu_result.get("error", "No content extracted")
                            }
                        })
                        
                except Exception as e:
                    logger.error(f"Failed to process result for {file_path}: {e}")
                    results["errors"] += 1
                    results["details"].append({
                        "file": str(file_path),
                        "result": {"status": "error", "error": str(e)}
                    })
            
            logger.info(f"Advanced parallel processing completed: {results['processed']} processed, {results['skipped']} skipped, {results['errors']} errors")
            return results
            
        except Exception as e:
            logger.error(f"Advanced parallel processing failed: {e}")
            raise

    def process_folder_parallel(self, folder_path: str, recursive: bool = True, max_workers: int = 2) -> Dict[str, Any]:
        """Process multiple documents in parallel."""
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
        
        logger.info(f"Found {len(files)} files to process in {folder_path} using {max_workers} workers")
        
        results = {
            "total_files": len(files),
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "details": []
        }
        
        def process_single_file(file_path):
            try:
                # Use relative path as document ID
                relative_path = file_path.relative_to(folder_path)
                document_id = str(relative_path).replace('/', '_').replace('\\', '_')
                
                result = self.process_file(file_path, document_id)
                return {
                    "file": str(file_path),
                    "document_id": document_id,
                    "result": result
                }
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                return {
                    "file": str(file_path),
                    "result": {"status": "error", "error": str(e)}
                }
        
        # Process files in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(process_single_file, file_path): file_path for file_path in files}
            
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    file_result = future.result()
                    results["details"].append(file_result)
                    
                    status = file_result["result"]["status"]
                    if status == "success":
                        results["processed"] += 1
                    elif status == "skipped":
                        results["skipped"] += 1
                    else:
                        results["errors"] += 1
                    
                    # Progress logging
                    total_completed = results["processed"] + results["skipped"] + results["errors"]
                    logger.info(f"Completed {total_completed}/{len(files)} files")
                        
                except Exception as e:
                    logger.error(f"Failed to process {file_path}: {e}")
                    results["errors"] += 1
                    results["details"].append({
                        "file": str(file_path),
                        "result": {"status": "error", "error": str(e)}
                    })
        
        return results

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
        """Delete a document and its vectors from S3 Vector bucket."""
        logger.info(f"Deleting document: {document_id}")
        
        try:
            # Get bucket names with retry logic
            vector_bucket, metadata_bucket = self._get_bucket_names()
            
            # Set environment variables for S3 Vector utils
            os.environ["VECTOR_BUCKET_NAME"] = vector_bucket
            os.environ["VECTOR_INDEX_NAME"] = self.config["vectorIndex"]["name"]
            
            # Import S3 Vector utilities
            try:
                import sys
                backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'backend')
                if backend_path not in sys.path:
                    sys.path.insert(0, backend_path)
                
                from s3_vector_utils import delete_document_vectors
                
                # Delete vectors using S3 Vector API
                success = delete_document_vectors(document_id)
                if not success:
                    logger.warning(f"Failed to delete vectors for document {document_id}")
                
            except ImportError as e:
                logger.warning(f"S3 Vector utilities not available ({e}), skipping vector deletion")
            
            # Delete metadata from S3 bucket with retry logic
            def _delete_metadata():
                s3_client = self._get_s3_client()
                try:
                    s3_client.delete_object(Bucket=metadata_bucket, Key=f"{document_id}.json")
                except:
                    pass  # Metadata might not exist
            
            self._retry_with_refresh(_delete_metadata)
            
            logger.info(f"Successfully deleted document: {document_id}")
            return {"status": "success", "document_id": document_id}
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return {"status": "error", "document_id": document_id, "error": str(e)}
            return {"status": "error", "error": str(e)}

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Process documents locally and upload to S3 (with automatic AWS token renewal)")
    parser.add_argument("--file", help="Process a single file")
    parser.add_argument("--folder", help="Process all files in a folder")
    parser.add_argument("--recursive", action="store_true", help="Process folder recursively")
    parser.add_argument("--document-id", help="Document ID for single file processing")
    parser.add_argument("--delete", help="Delete a document by ID")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--batch", action="store_true", help="Enable batch processing mode")
    parser.add_argument("--parallel", action="store_true", help="Enable parallel processing for folders (Phase 1)")
    parser.add_argument("--advanced", action="store_true", help="Enable advanced parallel processing (Phase 2)")
    parser.add_argument("--workers", type=int, default=2, help="Number of parallel workers for folder processing (default: 2)")
    
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
            # Choose processing mode
            if args.advanced:
                logger.info("Using advanced parallel processing (Phase 2 optimization)")
                result = processor.process_folder_advanced_parallel(args.folder, args.recursive)
            elif args.parallel:
                logger.info("Using parallel folder processing (Phase 1 optimization)")
                result = processor.process_folder_parallel(args.folder, args.recursive, args.workers)
            else:
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
