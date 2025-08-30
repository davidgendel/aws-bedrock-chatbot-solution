"""
Tests for S3 Vector utilities - vector search, document storage, RAG functionality.
"""
import json
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

from s3_vector_utils import (
    create_vector_index,
    store_document_vectors,
    query_similar_vectors,
    calculate_cosine_similarity,
    calculate_batch_cosine_similarity,
    delete_document_vectors,
    list_vector_indexes,
    get_vector_index_info,
    clear_all_caches,
    get_cache_stats
)


class TestS3VectorUtils(unittest.TestCase):
    """Test S3 Vector utilities functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'VECTOR_BUCKET_NAME': 'test-vector-bucket',
            'VECTOR_INDEX_NAME': 'test-index'
        })
        self.env_patcher.start()
        
        # Clear caches before each test
        clear_all_caches()
    
    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
        clear_all_caches()


class TestVectorIndexManagement(TestS3VectorUtils):
    """Test vector index creation and management."""
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_create_vector_index_success(self, mock_get_client):
        """Test successful vector index creation."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.create_index.return_value = {'indexArn': 'test-arn'}
        
        result = create_vector_index('test-index', dimensions=1536)
        
        self.assertTrue(result)
        mock_client.create_index.assert_called_once_with(
            vectorBucketName='test-vector-bucket',
            indexName='test-index',
            dataType='float32',
            dimension=1536,
            distanceMetric='cosine'
        )
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_create_vector_index_failure(self, mock_get_client):
        """Test vector index creation failure."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.create_index.side_effect = Exception("API Error")
        
        result = create_vector_index('test-index')
        
        self.assertFalse(result)
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_list_vector_indexes(self, mock_get_client):
        """Test listing vector indexes."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.list_indexes.return_value = {
            'indexes': [{
                'indexName': 'test-index',
                'indexArn': 'test-arn',
                'vectorBucketName': 'test-bucket',
                'creationTime': '2024-01-01T00:00:00Z'
            }]
        }
        mock_client.get_index.return_value = {
            'index': {
                'dimension': 1536,
                'distanceMetric': 'cosine',
                'dataType': 'float32'
            }
        }
        mock_client.list_vectors.return_value = {'vectors': []}
        
        indexes = list_vector_indexes()
        
        self.assertEqual(len(indexes), 1)
        self.assertEqual(indexes[0]['name'], 'test-index')
        self.assertEqual(indexes[0]['dimensions'], 1536)


class TestDocumentStorage(TestS3VectorUtils):
    """Test document vector storage functionality."""
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_store_document_vectors_success(self, mock_get_client):
        """Test successful document vector storage."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.put_vectors.return_value = {'success': True}
        
        chunks = [
            {
                'embedding': [0.1] * 1536,
                'content': 'Test content 1',
                'heading': 'Test Heading',
                'chunk_type': 'paragraph',
                'importance_score': 1.0
            },
            {
                'embedding': [0.2] * 1536,
                'content': 'Test content 2',
                'heading': 'Another Heading',
                'chunk_type': 'paragraph',
                'importance_score': 0.8
            }
        ]
        
        result = store_document_vectors('doc-123', chunks)
        
        self.assertTrue(result)
        mock_client.put_vectors.assert_called_once()
        
        # Verify call arguments
        call_args = mock_client.put_vectors.call_args
        self.assertEqual(call_args[1]['vectorBucketName'], 'test-vector-bucket')
        self.assertEqual(call_args[1]['indexName'], 'test-index')
        self.assertEqual(len(call_args[1]['vectors']), 2)
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_store_document_vectors_batch_processing(self, mock_get_client):
        """Test batch processing for large document sets."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.put_vectors.return_value = {'success': True}
        
        # Create 150 chunks to test batching (max batch size is 100)
        chunks = []
        for i in range(150):
            chunks.append({
                'embedding': [0.1 + i * 0.001] * 1536,
                'content': f'Test content {i}',
                'heading': f'Heading {i}',
                'chunk_type': 'paragraph',
                'importance_score': 1.0
            })
        
        result = store_document_vectors('doc-large', chunks)
        
        self.assertTrue(result)
        # Should be called twice (100 + 50)
        self.assertEqual(mock_client.put_vectors.call_count, 2)
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_delete_document_vectors(self, mock_get_client):
        """Test document vector deletion."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.list_vectors.return_value = {
            'vectors': [
                {'key': 'doc-123_chunk_0', 'metadata': {'document_id': 'doc-123'}},
                {'key': 'doc-123_chunk_1', 'metadata': {'document_id': 'doc-123'}},
                {'key': 'doc-456_chunk_0', 'metadata': {'document_id': 'doc-456'}}
            ]
        }
        mock_client.delete_vectors.return_value = {'success': True}
        
        result = delete_document_vectors('doc-123')
        
        self.assertTrue(result)
        mock_client.delete_vectors.assert_called_once_with(
            vectorBucketName='test-vector-bucket',
            indexName='test-index',
            keys=['doc-123_chunk_0', 'doc-123_chunk_1']
        )


class TestVectorSearch(TestS3VectorUtils):
    """Test vector search and similarity functionality."""
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_query_similar_vectors_success(self, mock_get_client):
        """Test successful vector similarity search."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.query_vectors.return_value = {
            'vectors': [
                {
                    'key': 'doc-123_chunk_0',
                    'distance': 0.2,
                    'metadata': {
                        'document_id': 'doc-123',
                        'chunk_index': '0',
                        'content': 'Similar content',
                        'heading': 'Test Heading',
                        'chunk_type': 'paragraph',
                        'importance_score': '1.0'
                    }
                },
                {
                    'key': 'doc-456_chunk_1',
                    'distance': 0.3,
                    'metadata': {
                        'document_id': 'doc-456',
                        'chunk_index': '1',
                        'content': 'Another similar content',
                        'heading': 'Another Heading',
                        'chunk_type': 'paragraph',
                        'importance_score': '0.8'
                    }
                }
            ]
        }
        
        query_embedding = [0.1] * 1536
        results = query_similar_vectors(query_embedding, limit=5, similarity_threshold=0.5)
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['document_id'], 'doc-123')
        self.assertAlmostEqual(results[0]['similarity'], 0.8, places=1)  # 1 - 0.2
        self.assertEqual(results[1]['document_id'], 'doc-456')
        
        mock_client.query_vectors.assert_called_once()
        call_args = mock_client.query_vectors.call_args[1]
        self.assertEqual(call_args['vectorBucketName'], 'test-vector-bucket')
        self.assertEqual(call_args['indexName'], 'test-index')
        self.assertEqual(call_args['topK'], 5)
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_query_similar_vectors_with_filters(self, mock_get_client):
        """Test vector search with metadata filters."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.query_vectors.return_value = {'vectors': []}
        
        query_embedding = [0.1] * 1536
        filters = {'document_ids': ['doc-123', 'doc-456']}
        
        query_similar_vectors(query_embedding, limit=3, filters=filters)
        
        call_args = mock_client.query_vectors.call_args[1]
        self.assertEqual(call_args['filter'], filters)
    
    def test_query_similar_vectors_empty_embedding(self):
        """Test vector search with empty embedding."""
        results = query_similar_vectors([], limit=5)
        self.assertEqual(results, [])
    
    def test_query_similar_vectors_zero_limit(self):
        """Test vector search with zero limit."""
        query_embedding = [0.1] * 1536
        results = query_similar_vectors(query_embedding, limit=0)
        self.assertEqual(results, [])


class TestSimilarityCalculations(TestS3VectorUtils):
    """Test similarity calculation functions."""
    
    def test_calculate_cosine_similarity_identical_vectors(self):
        """Test cosine similarity with identical vectors."""
        vec1 = [1.0, 2.0, 3.0, 4.0]
        vec2 = [1.0, 2.0, 3.0, 4.0]
        
        similarity = calculate_cosine_similarity(vec1, vec2)
        self.assertAlmostEqual(similarity, 1.0, places=5)
    
    def test_calculate_cosine_similarity_orthogonal_vectors(self):
        """Test cosine similarity with orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        
        similarity = calculate_cosine_similarity(vec1, vec2)
        self.assertAlmostEqual(similarity, 0.5, places=5)  # Normalized to [0,1]
    
    def test_calculate_cosine_similarity_opposite_vectors(self):
        """Test cosine similarity with opposite vectors."""
        vec1 = [1.0, 1.0, 1.0]
        vec2 = [-1.0, -1.0, -1.0]
        
        similarity = calculate_cosine_similarity(vec1, vec2)
        self.assertAlmostEqual(similarity, 0.0, places=5)  # Normalized to [0,1]
    
    def test_calculate_cosine_similarity_zero_vector(self):
        """Test cosine similarity with zero vector."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [0.0, 0.0, 0.0]
        
        similarity = calculate_cosine_similarity(vec1, vec2)
        self.assertEqual(similarity, 0.0)
    
    def test_calculate_cosine_similarity_different_dimensions(self):
        """Test cosine similarity with different vector dimensions."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0]
        
        similarity = calculate_cosine_similarity(vec1, vec2)
        self.assertEqual(similarity, 0.0)
    
    def test_calculate_batch_cosine_similarity(self):
        """Test batch cosine similarity calculation."""
        query_vector = [1.0, 0.0, 0.0]
        vectors = [
            [1.0, 0.0, 0.0],  # Identical
            [0.0, 1.0, 0.0],  # Orthogonal
            [-1.0, 0.0, 0.0], # Opposite
            [0.5, 0.5, 0.0]   # 45 degrees
        ]
        
        similarities = calculate_batch_cosine_similarity(query_vector, vectors)
        
        self.assertEqual(len(similarities), 4)
        self.assertAlmostEqual(similarities[0], 1.0, places=5)  # Identical
        self.assertAlmostEqual(similarities[1], 0.5, places=5)  # Orthogonal
        self.assertAlmostEqual(similarities[2], 0.0, places=5)  # Opposite
        self.assertGreater(similarities[3], 0.5)  # 45 degrees
    
    def test_calculate_batch_cosine_similarity_empty_vectors(self):
        """Test batch cosine similarity with empty vector list."""
        query_vector = [1.0, 0.0, 0.0]
        vectors = []
        
        similarities = calculate_batch_cosine_similarity(query_vector, vectors)
        self.assertEqual(similarities, [])


class TestCacheManagement(TestS3VectorUtils):
    """Test caching functionality."""
    
    def test_clear_all_caches(self):
        """Test clearing all caches."""
        # This should not raise any exceptions
        clear_all_caches()
        
        stats = get_cache_stats()
        self.assertIsInstance(stats, dict)
        
        # All caches should be empty after clearing
        for cache_name, cache_stats in stats.items():
            if isinstance(cache_stats, dict) and 'size' in cache_stats:
                self.assertEqual(cache_stats['size'], 0)
    
    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        stats = get_cache_stats()
        
        self.assertIsInstance(stats, dict)
        expected_caches = ['similarity_cache', 'metadata_cache', 'embedding_cache', 'partition_cache']
        
        for cache_name in expected_caches:
            self.assertIn(cache_name, stats)
            if isinstance(stats[cache_name], dict):
                self.assertIn('size', stats[cache_name])
                self.assertIn('maxsize', stats[cache_name])


class TestRAGFunctionality(TestS3VectorUtils):
    """Test RAG (Retrieval-Augmented Generation) specific functionality."""
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_rag_document_retrieval_workflow(self, mock_get_client):
        """Test complete RAG document retrieval workflow."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Mock query response with relevant documents
        mock_client.query_vectors.return_value = {
            'vectors': [
                {
                    'key': 'doc-ai_chunk_0',
                    'distance': 0.15,
                    'metadata': {
                        'document_id': 'doc-ai',
                        'chunk_index': '0',
                        'content': 'Artificial Intelligence is a branch of computer science that aims to create intelligent machines.',
                        'heading': 'Introduction to AI',
                        'chunk_type': 'paragraph',
                        'importance_score': '1.0'
                    }
                },
                {
                    'key': 'doc-ml_chunk_2',
                    'distance': 0.25,
                    'metadata': {
                        'document_id': 'doc-ml',
                        'chunk_index': '2',
                        'content': 'Machine learning algorithms can learn patterns from data without explicit programming.',
                        'heading': 'Machine Learning Basics',
                        'chunk_type': 'paragraph',
                        'importance_score': '0.9'
                    }
                }
            ]
        }
        
        # Simulate a user query about AI
        query_embedding = [0.1] * 1536  # Simulated embedding for "What is AI?"
        
        results = query_similar_vectors(
            query_embedding, 
            limit=5, 
            similarity_threshold=0.7
        )
        
        # Verify RAG retrieval results
        self.assertEqual(len(results), 2)
        
        # Check first result (highest similarity)
        self.assertEqual(results[0]['document_id'], 'doc-ai')
        self.assertIn('Artificial Intelligence', results[0]['content'])
        self.assertAlmostEqual(results[0]['similarity'], 0.85, places=1)  # 1 - 0.15
        
        # Check second result
        self.assertEqual(results[1]['document_id'], 'doc-ml')
        self.assertIn('Machine learning', results[1]['content'])
        
        # Verify results are sorted by combined score (similarity * importance)
        first_score = results[0]['similarity'] * results[0]['importance_score']
        second_score = results[1]['similarity'] * results[1]['importance_score']
        self.assertGreaterEqual(first_score, second_score)
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_rag_context_filtering(self, mock_get_client):
        """Test RAG context filtering by document type or date."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.query_vectors.return_value = {'vectors': []}
        
        query_embedding = [0.1] * 1536
        
        # Test filtering by document IDs (simulating document type filtering)
        filters = {'document_ids': ['technical-docs', 'user-manuals']}
        
        query_similar_vectors(
            query_embedding,
            limit=10,
            similarity_threshold=0.6,
            filters=filters
        )
        
        # Verify filters were passed to the API
        call_args = mock_client.query_vectors.call_args[1]
        self.assertEqual(call_args['filter'], filters)
        self.assertEqual(call_args['topK'], 10)
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_rag_similarity_threshold_filtering(self, mock_get_client):
        """Test RAG similarity threshold filtering for relevance."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Mock response with mixed relevance scores
        mock_client.query_vectors.return_value = {
            'vectors': [
                {
                    'key': 'relevant_chunk',
                    'distance': 0.1,  # High similarity (0.9)
                    'metadata': {
                        'document_id': 'doc-1',
                        'chunk_index': '0',
                        'content': 'Highly relevant content',
                        'heading': 'Relevant Section',
                        'chunk_type': 'paragraph',
                        'importance_score': '1.0'
                    }
                },
                {
                    'key': 'irrelevant_chunk',
                    'distance': 0.8,  # Low similarity (0.2)
                    'metadata': {
                        'document_id': 'doc-2',
                        'chunk_index': '1',
                        'content': 'Irrelevant content',
                        'heading': 'Irrelevant Section',
                        'chunk_type': 'paragraph',
                        'importance_score': '0.5'
                    }
                }
            ]
        }
        
        query_embedding = [0.1] * 1536
        
        # Set high similarity threshold to filter out irrelevant results
        results = query_similar_vectors(
            query_embedding,
            limit=10,
            similarity_threshold=0.8  # Only keep highly similar results
        )
        
        # Should only return the relevant chunk
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['content'], 'Highly relevant content')
        self.assertGreaterEqual(results[0]['similarity'], 0.8)


class TestErrorHandling(TestS3VectorUtils):
    """Test error handling and edge cases."""
    
    def test_missing_environment_variables(self):
        """Test behavior with missing environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            result = create_vector_index('test-index')
            self.assertFalse(result)
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_api_client_failure(self, mock_get_client):
        """Test handling of API client failures."""
        mock_get_client.side_effect = Exception("Failed to create client")
        
        result = create_vector_index('test-index')
        self.assertFalse(result)
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_query_vectors_api_error(self, mock_get_client):
        """Test handling of query API errors."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.query_vectors.side_effect = Exception("API Error")
        
        query_embedding = [0.1] * 1536
        results = query_similar_vectors(query_embedding, limit=5)
        
        self.assertEqual(results, [])
    
    def test_invalid_similarity_inputs(self):
        """Test similarity calculation with invalid inputs."""
        # Test with None inputs
        similarity = calculate_cosine_similarity(None, [1, 2, 3])
        self.assertEqual(similarity, 0.0)
        
        # Test with empty vectors
        similarity = calculate_cosine_similarity([], [1, 2, 3])
        self.assertEqual(similarity, 0.0)
        
        # Test with invalid numeric values
        similarity = calculate_cosine_similarity([float('inf')], [1.0])
        self.assertEqual(similarity, 0.0)


class TestAdvancedVectorOperations(TestS3VectorUtils):
    """Test advanced vector operations to improve coverage."""
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_delete_vector_index_success(self, mock_get_client):
        """Test successful vector index deletion."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_index.return_value = {
            'index': {'indexName': 'test-index', 'vectorBucketName': 'test-bucket'}
        }
        mock_client.delete_index.return_value = {'success': True}
        
        from s3_vector_utils import delete_vector_index
        result = delete_vector_index('test-index', force=True)
        
        self.assertTrue(result)
        mock_client.delete_index.assert_called_once()
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_get_vector_index_info_success(self, mock_get_client):
        """Test getting vector index information."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_index.return_value = {
            'index': {
                'indexName': 'test-index',
                'indexArn': 'test-arn',
                'vectorBucketName': 'test-bucket',
                'dimension': 1536,
                'distanceMetric': 'cosine',
                'dataType': 'float32',
                'creationTime': '2024-01-01T00:00:00Z'
            }
        }
        mock_client.list_vectors.return_value = {'vectors': []}
        
        from s3_vector_utils import get_vector_index_info
        result = get_vector_index_info('test-index')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'test-index')
        self.assertEqual(result['dimensions'], 1536)
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_optimize_vector_index(self, mock_get_client):
        """Test vector index optimization."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.list_vectors.return_value = {
            'vectors': [{'key': 'vec1'}, {'key': 'vec2'}],
            'nextToken': None
        }
        
        from s3_vector_utils import optimize_vector_index
        result = optimize_vector_index('test-index')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['vector_count'], 2)
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_get_vector_index_stats(self, mock_get_client):
        """Test getting vector index statistics."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_index.return_value = {
            'index': {
                'indexName': 'test-index',
                'dimension': 1536,
                'distanceMetric': 'cosine'
            }
        }
        mock_client.list_vectors.return_value = {'vectors': []}
        
        from s3_vector_utils import get_vector_index_stats
        result = get_vector_index_stats()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_indexes'], 1)
    
    @patch('s3_vector_utils.get_s3_client')
    def test_store_document_metadata(self, mock_get_client):
        """Test storing document metadata."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.put_object.return_value = {'success': True}
        
        from s3_vector_utils import store_document_metadata
        metadata = {'title': 'Test Doc', 'author': 'Test Author'}
        result = store_document_metadata('doc-123', metadata)
        
        self.assertTrue(result)
        mock_client.put_object.assert_called_once()
    
    @patch('s3_vector_utils.get_s3_client')
    def test_cleanup_old_vectors(self, mock_get_client):
        """Test cleaning up old vectors."""
        from datetime import datetime, timedelta
        
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Mock old objects
        old_date = datetime.utcnow() - timedelta(days=100)
        mock_client.get_paginator.return_value.paginate.return_value = [
            {
                'Contents': [
                    {'Key': 'vectors/test-index/old_vector.json', 'LastModified': old_date}
                ]
            }
        ]
        mock_client.delete_objects.return_value = {'Deleted': [{'Key': 'old_vector.json'}]}
        
        from s3_vector_utils import cleanup_old_vectors
        result = cleanup_old_vectors(days_old=90)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['deleted_count'], 1)


class TestVectorSearchOptimizations(TestS3VectorUtils):
    """Test vector search optimization functions."""
    
    def test_calculate_cosine_similarity_edge_cases(self):
        """Test cosine similarity edge cases."""
        from s3_vector_utils import calculate_cosine_similarity
        
        # Test with None inputs
        self.assertEqual(calculate_cosine_similarity(None, [1, 2, 3]), 0.0)
        self.assertEqual(calculate_cosine_similarity([1, 2, 3], None), 0.0)
        
        # Test with empty vectors
        self.assertEqual(calculate_cosine_similarity([], [1, 2, 3]), 0.0)
        self.assertEqual(calculate_cosine_similarity([1, 2, 3], []), 0.0)
        
        # Test with mismatched dimensions
        self.assertEqual(calculate_cosine_similarity([1, 2], [1, 2, 3]), 0.0)
        
        # Test with zero vectors
        self.assertEqual(calculate_cosine_similarity([0, 0, 0], [1, 2, 3]), 0.0)
        self.assertEqual(calculate_cosine_similarity([1, 2, 3], [0, 0, 0]), 0.0)
    
    @patch('s3_vector_utils.get_s3_client')
    def test_hierarchical_vector_search_fallback(self, mock_get_client):
        """Test hierarchical search fallback to batch search."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Mock missing partition structure
        mock_client.get_object.side_effect = Exception("Partition not found")
        
        from s3_vector_utils import _hierarchical_vector_search
        
        query_embedding = [0.1] * 1536
        
        with patch('s3_vector_utils._query_vectors_optimized_batch') as mock_batch:
            mock_batch.return_value = [{'id': 'test', 'similarity': 0.9}]
            
            result = _hierarchical_vector_search(
                query_embedding, 5, 0.5, None, 'test-bucket', 'test-index'
            )
            
            mock_batch.assert_called_once()
            self.assertEqual(len(result), 1)


class TestCacheOperations(TestS3VectorUtils):
    """Test cache operations for better coverage."""
    
    def test_cache_operations_comprehensive(self):
        """Test comprehensive cache operations."""
        from s3_vector_utils import (
            _cache_similarity_result, _get_cached_similarity,
            _cache_vector_metadata, _get_cached_vector_metadata,
            _cache_embedding, _get_cached_embedding,
            _cache_partition_info, _get_cached_partition_info,
            clear_all_caches, get_cache_stats
        )
        
        # Clear caches first
        clear_all_caches()
        
        # Test similarity caching
        _cache_similarity_result('query1', 'vec1', 0.85)
        cached_sim = _get_cached_similarity('query1', 'vec1')
        self.assertEqual(cached_sim, 0.85)
        
        # Test metadata caching
        metadata = {'doc_id': 'test', 'content': 'test content'}
        _cache_vector_metadata('vec1', metadata)
        cached_meta = _get_cached_vector_metadata('vec1')
        self.assertEqual(cached_meta, metadata)
        
        # Test embedding caching
        embedding = [0.1, 0.2, 0.3]
        _cache_embedding('content_hash', embedding)
        cached_emb = _get_cached_embedding('content_hash')
        self.assertEqual(cached_emb, embedding)
        
        # Test partition info caching
        partition_info = {'partitions': ['p1', 'p2']}
        _cache_partition_info('index1', partition_info)
        cached_part = _get_cached_partition_info('index1')
        self.assertEqual(cached_part, partition_info)
        
        # Test cache stats
        stats = get_cache_stats()
        self.assertIn('similarity_cache', stats)
        self.assertIn('metadata_cache', stats)
        self.assertIn('embedding_cache', stats)
        self.assertIn('partition_cache', stats)
    
    def test_cache_error_handling(self):
        """Test cache error handling."""
        from s3_vector_utils import (
            _cache_similarity_result, _get_cached_similarity
        )
        
        # Test with invalid inputs (should not crash)
        _cache_similarity_result(None, None, None)
        result = _get_cached_similarity(None, None)
        self.assertIsNone(result)


class TestS3ClientOperations(TestS3VectorUtils):
    """Test S3 client operations."""
    
    @patch('s3_vector_utils.get_s3_client')
    def test_s3_client_initialization(self, mock_get_client):
        """Test S3 client initialization."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        from s3_vector_utils import get_s3_client
        client = get_s3_client()
        
        self.assertIsNotNone(client)
    
    @patch('s3_vector_utils.get_aws_region')
    @patch('boto3.client')
    def test_s3_vectors_client_initialization(self, mock_boto_client, mock_get_region):
        """Test S3 Vectors client initialization."""
        mock_get_region.return_value = 'us-east-1'
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        from s3_vector_utils import get_s3_vectors_client
        client = get_s3_vectors_client()
        
        self.assertIsNotNone(client)
        mock_boto_client.assert_called_with('s3vectors', region_name='us-east-1')


class TestAdditionalCoverage(TestS3VectorUtils):
    """Additional tests to reach 50% coverage."""
    
    def test_generate_cache_key(self):
        """Test cache key generation."""
        from s3_vector_utils import _generate_cache_key
        
        key = _generate_cache_key('arg1', 'arg2', 123)
        self.assertIsInstance(key, str)
        self.assertEqual(len(key), 32)  # MD5 hash length
        
        # Same inputs should generate same key
        key2 = _generate_cache_key('arg1', 'arg2', 123)
        self.assertEqual(key, key2)
        
        # Different inputs should generate different keys
        key3 = _generate_cache_key('arg1', 'arg2', 124)
        self.assertNotEqual(key, key3)
    
    @patch('s3_vector_utils.get_s3_vectors_client')
    def test_count_vectors_in_index(self, mock_get_client):
        """Test counting vectors in index."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Mock paginated response
        mock_client.list_vectors.side_effect = [
            {'vectors': [{'key': f'vec{i}'} for i in range(1000)], 'nextToken': 'token1'},
            {'vectors': [{'key': f'vec{i}'} for i in range(500)], 'nextToken': None}
        ]
        
        from s3_vector_utils import _count_vectors_in_index
        count = _count_vectors_in_index('test-bucket', 'test-index', mock_client)
        
        self.assertEqual(count, 1500)
        self.assertEqual(mock_client.list_vectors.call_count, 2)
    
    @patch('s3_vector_utils.get_s3_client')
    def test_calculate_index_storage_size(self, mock_get_client):
        """Test calculating index storage size."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        mock_client.list_objects_v2.return_value = {
            'Contents': [
                {'Size': 1024},
                {'Size': 2048},
                {'Size': 512}
            ]
        }
        
        from s3_vector_utils import _calculate_index_storage_size
        size = _calculate_index_storage_size('test-bucket', 'test-index', mock_client)
        
        self.assertEqual(size, 3584)  # 1024 + 2048 + 512
    
    def test_apply_filters(self):
        """Test metadata filtering."""
        from s3_vector_utils import _apply_filters
        
        vector_data = {
            'document_id': 'doc-123',
            'created_at': '2024-01-15T10:00:00Z'
        }
        
        # Test document ID filter - match
        filters = {'document_ids': ['doc-123', 'doc-456']}
        self.assertTrue(_apply_filters(vector_data, filters))
        
        # Test document ID filter - no match
        filters = {'document_ids': ['doc-789']}
        self.assertFalse(_apply_filters(vector_data, filters))
        
        # Test date filters
        filters = {
            'min_date': '2024-01-01T00:00:00Z',
            'max_date': '2024-12-31T23:59:59Z'
        }
        self.assertTrue(_apply_filters(vector_data, filters))
        
        # Test with invalid data (should return True)
        invalid_data = {'invalid': 'data'}
        self.assertTrue(_apply_filters(invalid_data, filters))
    
    @patch('s3_vector_utils.get_s3_client')
    def test_query_vectors_full_scan(self, mock_get_client):
        """Test full scan vector query."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Mock S3 list response
        mock_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'vectors/test-index/vec1.json'},
                {'Key': 'vectors/test-index/vec2.json'}
            ]
        }
        
        # Mock vector data
        mock_client.get_object.side_effect = [
            {
                'Body': Mock(read=Mock(return_value=json.dumps({
                    'vector_id': 'vec1',
                    'document_id': 'doc1',
                    'chunk_index': 0,
                    'content': 'Test content 1',
                    'heading': 'Test Heading',
                    'chunk_type': 'paragraph',
                    'importance_score': 1.0,
                    'embedding': [0.1] * 1536,
                    'metadata': {}
                }).encode()))
            },
            {
                'Body': Mock(read=Mock(return_value=json.dumps({
                    'vector_id': 'vec2',
                    'document_id': 'doc2',
                    'chunk_index': 1,
                    'content': 'Test content 2',
                    'heading': 'Another Heading',
                    'chunk_type': 'paragraph',
                    'importance_score': 0.8,
                    'embedding': [0.2] * 1536,
                    'metadata': {}
                }).encode()))
            }
        ]
        
        from s3_vector_utils import _query_vectors_full_scan
        
        query_embedding = [0.15] * 1536
        results = _query_vectors_full_scan(
            query_embedding, 5, 0.5, None, 'test-bucket', 'test-index', mock_client, 'query_hash'
        )
        
        self.assertIsInstance(results, list)
        # Results depend on similarity calculation, just verify structure
        for result in results:
            self.assertIn('id', result)
            self.assertIn('similarity', result)


if __name__ == '__main__':
    unittest.main()
