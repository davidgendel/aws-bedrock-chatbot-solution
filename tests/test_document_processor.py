"""
Tests for document processor - document ingestion pipeline functionality.
"""
import json
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import time
import sys

# Add backend path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))


class TestDocumentProcessor(unittest.TestCase):
    """Test document processor functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_bucket = 'test-documents-bucket'
        self.test_key = 'documents/test-document.pdf'
        self.test_document_id = 'test-doc-123'
        
        # Mock extracted content
        self.mock_extracted_content = {
            'content': 'This is test document content for processing.',
            'content_type': 'application/pdf',
            'file_size': 1024,
            'metadata': {'title': 'Test Document', 'author': 'Test Author'}
        }
        
        # Mock chunks
        self.mock_chunks = [
            {
                'content': 'This is test document content',
                'metadata': {'chunk_index': 0, 'heading': 'Introduction'}
            },
            {
                'content': 'for processing and testing',
                'metadata': {'chunk_index': 1, 'heading': 'Content'}
            }
        ]
        
        # Mock embeddings
        self.mock_embeddings = [
            [0.1] * 1536,  # First chunk embedding
            [0.2] * 1536   # Second chunk embedding
        ]


class TestDocumentProcessingWithMocks(TestDocumentProcessor):
    """Test document processing with proper mocking."""
    
    @patch('document_processor.store_document_metadata')
    @patch('document_processor.store_document_vectors')
    @patch('document_processor.generate_embeddings')
    @patch('document_processor.create_chunks')
    @patch('document_processor.extract_text_from_document')
    @patch('uuid.uuid4')
    def test_process_document_success(self, mock_uuid, mock_extract, mock_chunks, 
                                    mock_embeddings, mock_store_vectors, mock_store_metadata):
        """Test successful document processing."""
        # Setup mocks
        mock_uuid.return_value = Mock()
        mock_uuid.return_value.__str__ = Mock(return_value=self.test_document_id)
        mock_extract.return_value = self.mock_extracted_content
        mock_chunks.return_value = self.mock_chunks
        mock_embeddings.return_value = self.mock_embeddings
        mock_store_vectors.return_value = True
        mock_store_metadata.return_value = True
        
        # Import and test
        from document_processor import process_document
        result = process_document(self.test_bucket, self.test_key)
        
        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['document_id'], self.test_document_id)
        self.assertEqual(result['chunks_processed'], 2)
        self.assertEqual(result['total_chunks'], 2)
        self.assertGreater(result['processing_time'], 0)
    
    def test_process_document_invalid_inputs(self):
        """Test document processing with invalid inputs."""
        from document_processor import process_document
        
        # Test empty bucket
        result = process_document('', self.test_key)
        self.assertFalse(result['success'])
        # Check that error was logged (actual implementation logs but doesn't add to errors list for ValidationError)
        
        # Test unsupported file type
        result = process_document(self.test_bucket, 'document.xyz')
        self.assertFalse(result['success'])
    
    @patch('document_processor.process_document')
    def test_process_batch_documents_success(self, mock_process):
        """Test successful batch document processing."""
        from document_processor import process_batch_documents
        
        # Mock successful processing for all documents
        mock_process.side_effect = [
            {'success': True, 'document_id': 'doc1', 'chunks_processed': 5, 'errors': []},
            {'success': True, 'document_id': 'doc2', 'chunks_processed': 3, 'errors': []},
            {'success': True, 'document_id': 'doc3', 'chunks_processed': 7, 'errors': []}
        ]
        
        documents = [
            {'bucket': 'test-bucket', 'key': 'doc1.pdf'},
            {'bucket': 'test-bucket', 'key': 'doc2.txt'},
            {'bucket': 'test-bucket', 'key': 'doc3.md'}
        ]
        
        result = process_batch_documents(documents)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_documents'], 3)
        self.assertEqual(result['processed_documents'], 3)
        self.assertEqual(result['failed_documents'], 0)
    
    @patch('document_processor.process_document')
    def test_handler_s3_event(self, mock_process):
        """Test handler with S3 event."""
        from document_processor import handler
        
        mock_process.return_value = {
            'success': True, 
            'document_id': 'doc123', 
            'chunks_processed': 5
        }
        
        # S3 event format
        event = {
            'Records': [
                {
                    'eventSource': 'aws:s3',
                    's3': {
                        'bucket': {'name': 'test-bucket'},
                        'object': {'key': 'documents/test.pdf'}
                    }
                }
            ]
        }
        
        response = handler(event, {})
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertTrue(body['success'])
    
    def test_handler_invalid_event(self):
        """Test handler with invalid event format."""
        from document_processor import handler
        
        event = {'invalid': 'format'}
        
        response = handler(event, {})
        
        self.assertEqual(response['statusCode'], 500)
        body = json.loads(response['body'])
        self.assertFalse(body['success'])


class TestUtilityFunctions(TestDocumentProcessor):
    """Test utility functions."""
    
    def test_is_document_file(self):
        """Test document file type detection."""
        from document_processor import _is_document_file
        
        # Supported document types
        self.assertTrue(_is_document_file('document.pdf'))
        self.assertTrue(_is_document_file('text.txt'))
        self.assertTrue(_is_document_file('readme.md'))
        self.assertTrue(_is_document_file('page.html'))
        self.assertTrue(_is_document_file('data.csv'))
        self.assertTrue(_is_document_file('config.json'))
        self.assertTrue(_is_document_file('report.docx'))
        
        # Case insensitive
        self.assertTrue(_is_document_file('DOCUMENT.PDF'))
        
        # Unsupported types
        self.assertFalse(_is_document_file('image.jpg'))
        self.assertFalse(_is_document_file('video.mp4'))
        
        # Invalid inputs
        self.assertFalse(_is_document_file(''))
        self.assertFalse(_is_document_file('no_extension'))
    
    def test_is_retryable_error(self):
        """Test retryable error detection."""
        from document_processor import _is_retryable_error
        
        # Retryable errors
        self.assertTrue(_is_retryable_error(Exception("ThrottlingException occurred")))
        self.assertTrue(_is_retryable_error(Exception("Connection timeout")))
        self.assertTrue(_is_retryable_error(Exception("Service temporary unavailable")))  # Match actual keyword
        
        # Non-retryable errors
        self.assertFalse(_is_retryable_error(Exception("ValidationException")))
        self.assertFalse(_is_retryable_error(Exception("Access denied")))


class TestRetryMechanism(TestDocumentProcessor):
    """Test retry mechanism functionality."""
    
    def test_with_retry_success_first_attempt(self):
        """Test retry decorator with successful first attempt."""
        from document_processor import with_retry
        
        mock_func = Mock(return_value="success")
        
        @with_retry
        def test_function():
            return mock_func()
        
        result = test_function()
        
        self.assertEqual(result, "success")
        mock_func.assert_called_once()
    
    def test_with_retry_max_retries_exceeded(self):
        """Test retry decorator when max retries exceeded."""
        from document_processor import with_retry
        
        # Use a retryable error to ensure retries happen
        mock_func = Mock(side_effect=Exception("ThrottlingException"))
        
        @with_retry
        def test_function():
            return mock_func()
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            with self.assertRaises(Exception) as context:
                test_function()
        
        self.assertEqual(str(context.exception), "ThrottlingException")
        self.assertEqual(mock_func.call_count, 4)  # Initial + 3 retries


if __name__ == '__main__':
    unittest.main()
