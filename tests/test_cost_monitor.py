"""
Tests for cost monitoring functionality.
"""
import json
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

from cost_monitor import (
    CostMonitor, MetricType, CostMetric, TokenUsage, ConversationCost,
    get_cost_monitor, track_tokens, track_vector_query, track_cache_hit,
    track_cache_miss, flush_cost_metrics, get_cost_summary
)
from metrics_collector import MetricsCollector, get_metrics_collector


class TestCostMonitor(unittest.TestCase):
    """Test cost monitoring functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'enabled': True,
            'cloudWatchNamespace': 'Test/Costs',
            'batchSize': 5,
            'flushInterval': 1,
            'trackConversationCosts': True
        }
        
        # Mock CloudWatch client
        self.mock_cloudwatch = Mock()
        
        with patch('cost_monitor.get_cloudwatch_client', return_value=self.mock_cloudwatch):
            self.cost_monitor = CostMonitor(self.config)
    
    def test_cost_monitor_initialization(self):
        """Test cost monitor initialization."""
        self.assertTrue(self.cost_monitor.enabled)
        self.assertEqual(self.cost_monitor.namespace, 'Test/Costs')
        self.assertEqual(self.cost_monitor.batch_size, 5)
        self.assertEqual(self.cost_monitor.flush_interval, 1)
    
    def test_token_usage_tracking(self):
        """Test token usage tracking."""
        token_usage = self.cost_monitor.track_token_usage(
            input_tokens=100,
            output_tokens=50,
            model_id='amazon.nova-lite-v1:0',
            conversation_id='test-conv-1'
        )
        
        self.assertEqual(token_usage.input_tokens, 100)
        self.assertEqual(token_usage.output_tokens, 50)
        self.assertEqual(token_usage.total_tokens, 150)
        self.assertEqual(token_usage.model_id, 'amazon.nova-lite-v1:0')
        self.assertFalse(token_usage.cached)
        self.assertGreater(token_usage.cost_estimate, 0)
        
        # Check conversation tracking
        conv_cost = self.cost_monitor.get_conversation_cost('test-conv-1')
        self.assertIsNotNone(conv_cost)
        self.assertEqual(conv_cost.total_tokens, 150)
        self.assertGreater(conv_cost.total_cost_estimate, 0)
    
    def test_vector_query_tracking(self):
        """Test vector query tracking."""
        cost = self.cost_monitor.track_vector_query(
            query_count=2,
            vectors_searched=100,
            cache_hit=False,
            conversation_id='test-conv-2'
        )
        
        self.assertGreater(cost, 0)
        
        # Check conversation tracking
        conv_cost = self.cost_monitor.get_conversation_cost('test-conv-2')
        self.assertIsNotNone(conv_cost)
        self.assertEqual(conv_cost.vector_queries, 2)
    
    def test_cache_performance_tracking(self):
        """Test cache performance tracking."""
        # Test cache hit
        self.cost_monitor.track_cache_performance(
            cache_type='response',
            hit=True,
            conversation_id='test-conv-3',
            cost_saved=0.001
        )
        
        # Test cache miss
        self.cost_monitor.track_cache_performance(
            cache_type='response',
            hit=False,
            conversation_id='test-conv-3'
        )
        
        # Check conversation tracking
        conv_cost = self.cost_monitor.get_conversation_cost('test-conv-3')
        self.assertIsNotNone(conv_cost)
        self.assertEqual(conv_cost.cache_hits, 1)
        self.assertEqual(conv_cost.cache_misses, 1)
    
    def test_api_call_tracking(self):
        """Test API call tracking."""
        self.cost_monitor.track_api_call(
            api_type='bedrock',
            duration_ms=150.5,
            conversation_id='test-conv-4'
        )
        
        # Should not raise any exceptions
        self.assertTrue(True)
    
    def test_cost_calculation(self):
        """Test cost calculation accuracy."""
        # Test Nova Lite pricing
        cost = self.cost_monitor._calculate_token_cost(1000, 500, 'amazon.nova-lite-v1:0')
        expected_cost = (1000 / 1000) * 0.00006 + (500 / 1000) * 0.00024
        self.assertAlmostEqual(cost, expected_cost, places=6)
        
        # Test Titan Embeddings pricing
        cost = self.cost_monitor._calculate_token_cost(1000, 0, 'amazon.titan-embed-text-v1')
        expected_cost = (1000 / 1000) * 0.0001
        self.assertAlmostEqual(cost, expected_cost, places=6)
    
    def test_cost_summary(self):
        """Test cost summary generation."""
        # Add some test data
        self.cost_monitor.track_token_usage(100, 50, 'amazon.nova-lite-v1:0', 'conv-1')
        self.cost_monitor.track_vector_query(1, 50, False, 'conv-1')
        self.cost_monitor.track_cache_performance('response', True, 'conv-1')
        
        summary = self.cost_monitor.get_cost_summary()
        
        self.assertIn('total_conversations', summary)
        self.assertIn('total_cost_estimate', summary)
        self.assertIn('total_tokens', summary)
        self.assertIn('total_vector_queries', summary)
        self.assertIn('cache_hit_rate', summary)
        self.assertIn('average_cost_per_conversation', summary)
        
        self.assertEqual(summary['total_conversations'], 1)
        self.assertGreater(summary['total_cost_estimate'], 0)
        self.assertEqual(summary['total_tokens'], 150)
        self.assertEqual(summary['total_vector_queries'], 1)
    
    @patch('cost_monitor.get_cloudwatch_client')
    def test_metrics_flushing(self, mock_get_client):
        """Test metrics flushing to CloudWatch."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Create cost monitor with mocked client
        cost_monitor = CostMonitor(self.config)
        
        # Add some metrics
        cost_monitor.track_token_usage(100, 50, 'amazon.nova-lite-v1:0')
        cost_monitor.track_vector_query(1, 50, False)
        
        # Flush metrics
        result = cost_monitor.flush_metrics(force=True)
        
        self.assertTrue(result)
        mock_client.put_metric_data.assert_called()
        
        # Check that metrics were sent
        call_args = mock_client.put_metric_data.call_args
        self.assertEqual(call_args[1]['Namespace'], 'Test/Costs')
        self.assertIn('MetricData', call_args[1])
        self.assertGreater(len(call_args[1]['MetricData']), 0)
    
    def test_disabled_cost_monitor(self):
        """Test cost monitor when disabled."""
        disabled_config = {'enabled': False}
        
        with patch('cost_monitor.get_cloudwatch_client'):
            disabled_monitor = CostMonitor(disabled_config)
        
        # All tracking should return default values
        token_usage = disabled_monitor.track_token_usage(100, 50, 'test-model')
        self.assertEqual(token_usage.total_tokens, 0)
        
        cost = disabled_monitor.track_vector_query(1)
        self.assertEqual(cost, 0.0)
        
        summary = disabled_monitor.get_cost_summary()
        self.assertEqual(summary, {})


class TestMetricsCollector(unittest.TestCase):
    """Test metrics collector functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'maxBatchSize': 5,
            'maxQueueSize': 100,
            'flushInterval': 1,
            'maxRequestsPerMinute': 10
        }
        self.collector = MetricsCollector(self.config)
    
    def test_collector_initialization(self):
        """Test collector initialization."""
        self.assertEqual(self.collector.max_batch_size, 5)
        self.assertEqual(self.collector.max_queue_size, 100)
        self.assertEqual(self.collector.flush_interval, 1)
        self.assertEqual(self.collector.max_requests_per_minute, 10)
    
    def test_metric_collection(self):
        """Test metric collection."""
        result = self.collector.collect_metric(
            namespace='Test/Namespace',
            metric_name='TestMetric',
            value=42.0,
            unit='Count',
            dimensions={'TestDim': 'TestValue'}
        )
        
        self.assertTrue(result)
        self.assertEqual(len(self.collector.metrics_queue), 1)
        self.assertEqual(self.collector.stats['metrics_collected'], 1)
    
    def test_queue_overflow(self):
        """Test queue overflow handling."""
        # Fill queue to capacity
        for i in range(self.collector.max_queue_size + 5):
            self.collector.collect_metric(
                namespace='Test',
                metric_name='TestMetric',
                value=i,
                unit='Count',
                dimensions={}
            )
        
        # Queue should not exceed max size
        self.assertEqual(len(self.collector.metrics_queue), self.collector.max_queue_size)
    
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        # Fill request timestamps to simulate rate limiting
        current_time = time.time()
        for i in range(self.collector.max_requests_per_minute):
            self.collector.request_timestamps.append(current_time)
        
        # Rate limit should be triggered
        self.assertFalse(self.collector._check_rate_limit())
        
        # Clear old timestamps
        self.collector.request_timestamps.clear()
        self.assertTrue(self.collector._check_rate_limit())
    
    def test_circuit_breaker(self):
        """Test circuit breaker functionality."""
        # Trigger circuit breaker
        for i in range(self.collector.max_errors):
            self.collector._handle_error()
        
        self.assertTrue(self.collector.circuit_open)
        
        # Reset circuit breaker
        self.collector._reset_circuit_breaker()
        self.assertFalse(self.collector.circuit_open)
        self.assertEqual(self.collector.error_count, 0)
    
    def test_stats_collection(self):
        """Test statistics collection."""
        # Add some metrics
        self.collector.collect_metric('Test', 'Metric1', 1.0, 'Count', {})
        self.collector.collect_metric('Test', 'Metric2', 2.0, 'Count', {})
        
        stats = self.collector.get_stats()
        
        self.assertIn('metrics_collected', stats)
        self.assertIn('queue_size', stats)
        self.assertIn('circuit_open', stats)
        self.assertIn('error_rate', stats)
        
        self.assertEqual(stats['metrics_collected'], 2)
        self.assertEqual(stats['queue_size'], 2)
        self.assertFalse(stats['circuit_open'])


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""
    
    @patch('cost_monitor.get_cost_monitor')
    def test_track_tokens_function(self, mock_get_monitor):
        """Test track_tokens convenience function."""
        mock_monitor = Mock()
        mock_monitor.track_token_usage.return_value = TokenUsage()
        mock_get_monitor.return_value = mock_monitor
        
        result = track_tokens(100, 50, 'test-model')
        
        mock_monitor.track_token_usage.assert_called_once_with(100, 50, 'test-model')
        self.assertIsInstance(result, TokenUsage)
    
    @patch('cost_monitor.get_cost_monitor')
    def test_track_vector_query_function(self, mock_get_monitor):
        """Test track_vector_query convenience function."""
        mock_monitor = Mock()
        mock_monitor.track_vector_query.return_value = 0.001
        mock_get_monitor.return_value = mock_monitor
        
        result = track_vector_query(2)
        
        mock_monitor.track_vector_query.assert_called_once_with(2)
        self.assertEqual(result, 0.001)
    
    @patch('cost_monitor.get_cost_monitor')
    def test_cache_tracking_functions(self, mock_get_monitor):
        """Test cache tracking convenience functions."""
        mock_monitor = Mock()
        mock_get_monitor.return_value = mock_monitor
        
        track_cache_hit('test_cache')
        mock_monitor.track_cache_performance.assert_called_with('test_cache', True)
        
        track_cache_miss('test_cache')
        mock_monitor.track_cache_performance.assert_called_with('test_cache', False)


class TestIntegration(unittest.TestCase):
    """Integration tests for cost monitoring."""
    
    @patch('cost_monitor.get_cloudwatch_client')
    def test_end_to_end_cost_tracking(self, mock_get_client):
        """Test end-to-end cost tracking scenario."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Simulate a conversation
        conversation_id = 'integration-test-conv'
        
        # Track embeddings generation
        track_tokens(50, 0, 'amazon.titan-embed-text-v1', conversation_id=conversation_id)
        
        # Track vector query
        track_vector_query(1, vectors_searched=100, conversation_id=conversation_id)
        
        # Track response generation
        track_tokens(200, 100, 'amazon.nova-lite-v1:0', conversation_id=conversation_id)
        
        # Track cache hit
        track_cache_hit('response_cache', conversation_id=conversation_id)
        
        # Get cost summary
        summary = get_cost_summary()
        
        # Verify tracking
        self.assertGreater(summary['total_conversations'], 0)
        self.assertGreater(summary['total_cost_estimate'], 0)
        self.assertGreater(summary['total_tokens'], 0)
        self.assertGreater(summary['total_vector_queries'], 0)
        
        # Flush metrics
        result = flush_cost_metrics(force=True)
        self.assertTrue(result)
        
        # Verify CloudWatch was called
        mock_client.put_metric_data.assert_called()


if __name__ == '__main__':
    unittest.main()
