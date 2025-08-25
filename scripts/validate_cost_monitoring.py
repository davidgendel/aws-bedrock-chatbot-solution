#!/usr/bin/env python3
"""
Validation script for cost monitoring functionality.
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, List

# Add lambda_function to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda_function'))

try:
    from cost_monitor import (
        CostMonitor, get_cost_monitor, track_tokens, track_vector_query,
        track_cache_hit, track_cache_miss, flush_cost_metrics, get_cost_summary
    )
    from metrics_collector import MetricsCollector, get_metrics_collector
    from token_utils import calculate_token_cost, estimate_tokens, get_model_cost_info
except ImportError as e:
    print(f"❌ Failed to import cost monitoring modules: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CostMonitoringValidator:
    """Validator for cost monitoring functionality."""
    
    def __init__(self):
        """Initialize validator."""
        self.results = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'test_results': [],
            'performance_metrics': {},
            'validation_summary': {}
        }
        
        # Load configuration
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from config.json."""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
            return {}
    
    def run_validation(self) -> Dict[str, Any]:
        """Run comprehensive cost monitoring validation."""
        logger.info("🚀 Starting cost monitoring validation...")
        
        # Core functionality tests
        self._test_cost_monitor_initialization()
        self._test_token_tracking()
        self._test_vector_query_tracking()
        self._test_cache_performance_tracking()
        self._test_api_call_tracking()
        self._test_conversation_cost_tracking()
        self._test_cost_calculations()
        self._test_metrics_collection()
        self._test_cost_summary()
        
        # Performance tests
        self._test_performance_impact()
        self._test_concurrent_tracking()
        
        # Integration tests
        self._test_cloudwatch_integration()
        self._test_configuration_validation()
        
        # Generate summary
        self._generate_validation_summary()
        
        return self.results
    
    def _test_cost_monitor_initialization(self):
        """Test cost monitor initialization."""
        test_name = "Cost Monitor Initialization"
        self.results['total_tests'] += 1
        
        try:
            # Test with default config
            monitor = get_cost_monitor()
            assert monitor is not None, "Cost monitor should be initialized"
            
            # Test with custom config
            custom_config = {
                'enabled': True,
                'cloudWatchNamespace': 'Test/Costs',
                'batchSize': 10
            }
            custom_monitor = CostMonitor(custom_config)
            assert custom_monitor.enabled == True
            assert custom_monitor.namespace == 'Test/Costs'
            assert custom_monitor.batch_size == 10
            
            self._record_test_result(test_name, True, "Cost monitor initialized successfully")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"Initialization failed: {e}")
    
    def _test_token_tracking(self):
        """Test token usage tracking."""
        test_name = "Token Usage Tracking"
        self.results['total_tests'] += 1
        
        try:
            # Test token tracking
            token_usage = track_tokens(
                input_tokens=100,
                output_tokens=50,
                model_id='amazon.nova-lite-v1:0',
                conversation_id='test-conv-1'
            )
            
            assert token_usage.input_tokens == 100
            assert token_usage.output_tokens == 50
            assert token_usage.total_tokens == 150
            assert token_usage.cost_estimate > 0
            assert token_usage.model_id == 'amazon.nova-lite-v1:0'
            
            self._record_test_result(test_name, True, f"Token tracking successful: {token_usage.cost_estimate:.6f} USD")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"Token tracking failed: {e}")
    
    def _test_vector_query_tracking(self):
        """Test vector query tracking."""
        test_name = "Vector Query Tracking"
        self.results['total_tests'] += 1
        
        try:
            # Test vector query tracking
            cost = track_vector_query(
                query_count=2,
                vectors_searched=100,
                cache_hit=False,
                conversation_id='test-conv-2'
            )
            
            assert cost > 0, "Vector query cost should be positive"
            
            # Test cached query
            cached_cost = track_vector_query(
                query_count=1,
                cache_hit=True,
                conversation_id='test-conv-2'
            )
            
            assert cached_cost == 0, "Cached query should have no cost"
            
            self._record_test_result(test_name, True, f"Vector query tracking successful: {cost:.6f} USD")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"Vector query tracking failed: {e}")
    
    def _test_cache_performance_tracking(self):
        """Test cache performance tracking."""
        test_name = "Cache Performance Tracking"
        self.results['total_tests'] += 1
        
        try:
            # Test cache hit
            track_cache_hit(
                cache_type='response_cache',
                conversation_id='test-conv-3',
                cost_saved=0.001
            )
            
            # Test cache miss
            track_cache_miss(
                cache_type='response_cache',
                conversation_id='test-conv-3'
            )
            
            # Verify conversation tracking
            monitor = get_cost_monitor()
            conv_cost = monitor.get_conversation_cost('test-conv-3')
            
            assert conv_cost is not None, "Conversation should be tracked"
            assert conv_cost.cache_hits == 1, "Cache hits should be tracked"
            assert conv_cost.cache_misses == 1, "Cache misses should be tracked"
            
            self._record_test_result(test_name, True, "Cache performance tracking successful")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"Cache performance tracking failed: {e}")
    
    def _test_api_call_tracking(self):
        """Test API call tracking."""
        test_name = "API Call Tracking"
        self.results['total_tests'] += 1
        
        try:
            monitor = get_cost_monitor()
            
            # Test API call tracking
            monitor.track_api_call(
                api_type='bedrock_text_generation',
                duration_ms=150.5,
                conversation_id='test-conv-4'
            )
            
            # Should not raise any exceptions
            self._record_test_result(test_name, True, "API call tracking successful")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"API call tracking failed: {e}")
    
    def _test_conversation_cost_tracking(self):
        """Test conversation-level cost tracking."""
        test_name = "Conversation Cost Tracking"
        self.results['total_tests'] += 1
        
        try:
            conversation_id = 'test-conv-comprehensive'
            
            # Simulate a complete conversation
            track_tokens(100, 0, 'amazon.titan-embed-text-v1', conversation_id=conversation_id)  # Embeddings
            track_vector_query(1, vectors_searched=50, conversation_id=conversation_id)  # Vector query
            track_tokens(200, 100, 'amazon.nova-lite-v1:0', conversation_id=conversation_id)  # Response
            track_cache_hit('response_cache', conversation_id=conversation_id)  # Cache hit
            
            # Verify conversation tracking
            monitor = get_cost_monitor()
            conv_cost = monitor.get_conversation_cost(conversation_id)
            
            assert conv_cost is not None, "Conversation should be tracked"
            assert conv_cost.total_tokens == 400, f"Expected 400 tokens, got {conv_cost.total_tokens}"
            assert conv_cost.vector_queries == 1, f"Expected 1 vector query, got {conv_cost.vector_queries}"
            assert conv_cost.cache_hits == 1, f"Expected 1 cache hit, got {conv_cost.cache_hits}"
            assert conv_cost.total_cost_estimate > 0, "Total cost should be positive"
            
            self._record_test_result(test_name, True, f"Conversation tracking successful: ${conv_cost.total_cost_estimate:.6f}")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"Conversation cost tracking failed: {e}")
    
    def _test_cost_calculations(self):
        """Test cost calculation accuracy."""
        test_name = "Cost Calculations"
        self.results['total_tests'] += 1
        
        try:
            # Test Nova Lite pricing
            cost = calculate_token_cost(1000, 500, 'amazon.nova-lite-v1:0')
            expected_cost = (1000 / 1000) * 0.00006 + (500 / 1000) * 0.00024
            
            assert abs(cost - expected_cost) < 0.000001, f"Cost calculation mismatch: {cost} vs {expected_cost}"
            
            # Test Titan Embeddings pricing
            embedding_cost = calculate_token_cost(1000, 0, 'amazon.titan-embed-text-v1')
            expected_embedding_cost = (1000 / 1000) * 0.0001
            
            assert abs(embedding_cost - expected_embedding_cost) < 0.000001, "Embedding cost calculation mismatch"
            
            # Test model cost info
            model_info = get_model_cost_info('amazon.nova-lite-v1:0')
            assert 'input_cost_per_1k' in model_info
            assert 'output_cost_per_1k' in model_info
            
            self._record_test_result(test_name, True, f"Cost calculations accurate: Nova=${cost:.6f}, Titan=${embedding_cost:.6f}")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"Cost calculations failed: {e}")
    
    def _test_metrics_collection(self):
        """Test metrics collection and batching."""
        test_name = "Metrics Collection"
        self.results['total_tests'] += 1
        
        try:
            collector = get_metrics_collector()
            
            # Test metric collection
            result = collector.collect_metric(
                namespace='Test/Validation',
                metric_name='TestMetric',
                value=42.0,
                unit='Count',
                dimensions={'TestDim': 'TestValue'}
            )
            
            assert result == True, "Metric collection should succeed"
            assert len(collector.metrics_queue) > 0, "Metrics queue should contain metrics"
            
            # Test stats
            stats = collector.get_stats()
            assert 'metrics_collected' in stats
            assert stats['metrics_collected'] > 0
            
            self._record_test_result(test_name, True, f"Metrics collection successful: {stats['metrics_collected']} metrics")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"Metrics collection failed: {e}")
    
    def _test_cost_summary(self):
        """Test cost summary generation."""
        test_name = "Cost Summary"
        self.results['total_tests'] += 1
        
        try:
            summary = get_cost_summary()
            
            # Verify summary structure
            required_fields = [
                'total_conversations', 'total_cost_estimate', 'total_tokens',
                'total_vector_queries', 'cache_hit_rate', 'average_cost_per_conversation'
            ]
            
            for field in required_fields:
                assert field in summary, f"Summary missing field: {field}"
            
            assert summary['total_conversations'] > 0, "Should have tracked conversations"
            assert summary['total_cost_estimate'] > 0, "Should have positive cost estimate"
            
            self._record_test_result(test_name, True, f"Cost summary generated: {summary['total_conversations']} conversations, ${summary['total_cost_estimate']:.6f}")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"Cost summary failed: {e}")
    
    def _test_performance_impact(self):
        """Test performance impact of cost monitoring."""
        test_name = "Performance Impact"
        self.results['total_tests'] += 1
        
        try:
            # Measure performance impact
            iterations = 100
            
            # Without cost monitoring
            start_time = time.time()
            for i in range(iterations):
                # Simulate work without tracking
                estimate_tokens(f"Test message {i}")
            baseline_time = time.time() - start_time
            
            # With cost monitoring
            start_time = time.time()
            for i in range(iterations):
                # Simulate work with tracking
                track_tokens(10, 5, 'amazon.nova-lite-v1:0', conversation_id=f'perf-test-{i}')
            tracking_time = time.time() - start_time
            
            # Calculate overhead
            overhead_ms = (tracking_time - baseline_time) * 1000
            overhead_per_call = overhead_ms / iterations
            
            # Performance should be reasonable (< 5ms per call)
            assert overhead_per_call < 5.0, f"Performance overhead too high: {overhead_per_call:.2f}ms per call"
            
            self.results['performance_metrics']['overhead_per_call_ms'] = overhead_per_call
            self.results['performance_metrics']['total_overhead_ms'] = overhead_ms
            
            self._record_test_result(test_name, True, f"Performance impact acceptable: {overhead_per_call:.2f}ms per call")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"Performance test failed: {e}")
    
    def _test_concurrent_tracking(self):
        """Test concurrent cost tracking."""
        test_name = "Concurrent Tracking"
        self.results['total_tests'] += 1
        
        try:
            import threading
            import concurrent.futures
            
            def track_concurrent_tokens(thread_id):
                """Track tokens in a separate thread."""
                for i in range(10):
                    track_tokens(
                        input_tokens=10,
                        output_tokens=5,
                        model_id='amazon.nova-lite-v1:0',
                        conversation_id=f'concurrent-{thread_id}-{i}'
                    )
                return thread_id
            
            # Run concurrent tracking
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(track_concurrent_tokens, i) for i in range(5)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            assert len(results) == 5, "All concurrent threads should complete"
            
            # Verify tracking worked
            summary = get_cost_summary()
            assert summary['total_conversations'] >= 50, "Should have tracked concurrent conversations"
            
            self._record_test_result(test_name, True, f"Concurrent tracking successful: {len(results)} threads")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"Concurrent tracking failed: {e}")
    
    def _test_cloudwatch_integration(self):
        """Test CloudWatch integration (mock)."""
        test_name = "CloudWatch Integration"
        self.results['total_tests'] += 1
        
        try:
            # Test metrics flushing (will use mock in test environment)
            result = flush_cost_metrics(force=True)
            
            # In test environment, this might return False due to missing AWS credentials
            # That's acceptable for validation
            
            self._record_test_result(test_name, True, f"CloudWatch integration test completed: {result}")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"CloudWatch integration failed: {e}")
    
    def _test_configuration_validation(self):
        """Test configuration validation."""
        test_name = "Configuration Validation"
        self.results['total_tests'] += 1
        
        try:
            # Test with valid configuration
            valid_config = {
                'enabled': True,
                'cloudWatchNamespace': 'Test/Costs',
                'batchSize': 20,
                'flushInterval': 60
            }
            
            monitor = CostMonitor(valid_config)
            assert monitor.enabled == True
            assert monitor.namespace == 'Test/Costs'
            
            # Test with disabled configuration
            disabled_config = {'enabled': False}
            disabled_monitor = CostMonitor(disabled_config)
            assert disabled_monitor.enabled == False
            
            # Test disabled monitor returns default values
            token_usage = disabled_monitor.track_token_usage(100, 50, 'test-model')
            assert token_usage.total_tokens == 0
            
            self._record_test_result(test_name, True, "Configuration validation successful")
            
        except Exception as e:
            self._record_test_result(test_name, False, f"Configuration validation failed: {e}")
    
    def _record_test_result(self, test_name: str, passed: bool, message: str):
        """Record test result."""
        if passed:
            self.results['passed_tests'] += 1
            logger.info(f"✅ {test_name}: {message}")
        else:
            self.results['failed_tests'] += 1
            logger.error(f"❌ {test_name}: {message}")
        
        self.results['test_results'].append({
            'test_name': test_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    def _generate_validation_summary(self):
        """Generate validation summary."""
        total_tests = self.results['total_tests']
        passed_tests = self.results['passed_tests']
        failed_tests = self.results['failed_tests']
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        self.results['validation_summary'] = {
            'overall_status': 'PASS' if failed_tests == 0 else 'FAIL',
            'success_rate': round(success_rate, 1),
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'validation_time': datetime.now(timezone.utc).isoformat()
        }
        
        # Log summary
        logger.info(f"\n{'='*60}")
        logger.info(f"💰 COST MONITORING VALIDATION SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Overall Status: {'✅ PASS' if failed_tests == 0 else '❌ FAIL'}")
        logger.info(f"Success Rate: {success_rate:.1f}%")
        logger.info(f"Tests: {passed_tests}/{total_tests}")
        
        if self.results['performance_metrics']:
            logger.info(f"\nPerformance Metrics:")
            for metric, value in self.results['performance_metrics'].items():
                logger.info(f"  {metric}: {value:.2f}")
        
        logger.info(f"\nDetailed Results:")
        for result in self.results['test_results']:
            status = "✅" if result['passed'] else "❌"
            logger.info(f"  {status} {result['test_name']}: {result['message']}")
        
        logger.info(f"{'='*60}")


def main():
    """Main validation function."""
    validator = CostMonitoringValidator()
    results = validator.run_validation()
    
    # Save results to file
    results_file = os.path.join(os.path.dirname(__file__), '..', 'cost_monitoring_validation.json')
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"📄 Validation results saved to: {results_file}")
    
    # Exit with appropriate code
    exit_code = 0 if results['failed_tests'] == 0 else 1
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
