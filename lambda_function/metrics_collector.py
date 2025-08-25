"""
Metrics aggregation and batching system for cost monitoring.
"""
import json
import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)


@dataclass
class MetricBatch:
    """Batch of metrics for efficient processing."""
    namespace: str
    metrics: List[Dict[str, Any]]
    timestamp: datetime
    batch_id: str


class MetricsCollector:
    """
    Advanced metrics collection and batching system.
    
    Features:
    - Intelligent batching to reduce CloudWatch API calls
    - Rate limiting protection
    - Metric aggregation and deduplication
    - Background processing to minimize latency impact
    - Circuit breaker for error handling
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize metrics collector."""
        self.config = config or {}
        
        # Configuration
        self.max_batch_size = self.config.get('maxBatchSize', 20)
        self.max_queue_size = self.config.get('maxQueueSize', 1000)
        self.flush_interval = self.config.get('flushInterval', 30)
        self.aggregation_window = self.config.get('aggregationWindow', 60)
        
        # Rate limiting
        self.max_requests_per_minute = self.config.get('maxRequestsPerMinute', 150)  # CloudWatch limit is 150/min
        self.request_timestamps = deque(maxlen=self.max_requests_per_minute)
        
        # Metrics storage
        self.metrics_queue = deque(maxlen=self.max_queue_size)
        self.aggregated_metrics = defaultdict(list)
        self.queue_lock = threading.RLock()
        
        # Background processing
        self.processing_thread = None
        self.stop_processing = threading.Event()
        self.last_flush = time.time()
        
        # Circuit breaker
        self.error_count = 0
        self.max_errors = self.config.get('maxErrors', 10)
        self.circuit_open = False
        self.circuit_reset_time = 0
        self.circuit_timeout = self.config.get('circuitTimeout', 300)  # 5 minutes
        
        # Statistics
        self.stats = {
            'metrics_collected': 0,
            'metrics_sent': 0,
            'batches_sent': 0,
            'errors': 0,
            'circuit_breaks': 0,
            'rate_limits': 0
        }
        
        logger.info("Metrics collector initialized")
    
    def start_background_processing(self):
        """Start background processing thread."""
        if self.processing_thread and self.processing_thread.is_alive():
            return
        
        self.stop_processing.clear()
        self.processing_thread = threading.Thread(
            target=self._background_processor,
            daemon=True,
            name="MetricsCollector"
        )
        self.processing_thread.start()
        logger.info("Background metrics processing started")
    
    def stop_background_processing(self):
        """Stop background processing thread."""
        if self.processing_thread and self.processing_thread.is_alive():
            self.stop_processing.set()
            self.processing_thread.join(timeout=5)
            logger.info("Background metrics processing stopped")
    
    def collect_metric(
        self,
        namespace: str,
        metric_name: str,
        value: float,
        unit: str,
        dimensions: Dict[str, str],
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Collect a metric for processing.
        
        Args:
            namespace: CloudWatch namespace
            metric_name: Name of the metric
            value: Metric value
            unit: Unit of measurement
            dimensions: Metric dimensions
            timestamp: Optional timestamp (defaults to now)
            metadata: Additional metadata
            
        Returns:
            True if metric was collected successfully
        """
        if self.circuit_open:
            if time.time() < self.circuit_reset_time:
                return False
            else:
                self._reset_circuit_breaker()
        
        try:
            if timestamp is None:
                timestamp = datetime.now(timezone.utc)
            
            metric = {
                'namespace': namespace,
                'metric_name': metric_name,
                'value': value,
                'unit': unit,
                'dimensions': dimensions,
                'timestamp': timestamp,
                'metadata': metadata or {}
            }
            
            with self.queue_lock:
                if len(self.metrics_queue) >= self.max_queue_size:
                    # Remove oldest metric to make room
                    self.metrics_queue.popleft()
                    logger.warning("Metrics queue full, dropping oldest metric")
                
                self.metrics_queue.append(metric)
                self.stats['metrics_collected'] += 1
            
            # Start background processing if not already running
            if not self.processing_thread or not self.processing_thread.is_alive():
                self.start_background_processing()
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to collect metric: {e}")
            self._handle_error()
            return False
    
    def flush_metrics(self, force: bool = False) -> Tuple[bool, int]:
        """
        Flush metrics to CloudWatch.
        
        Args:
            force: Force flush regardless of timing
            
        Returns:
            Tuple of (success, metrics_sent)
        """
        if self.circuit_open and time.time() < self.circuit_reset_time:
            return False, 0
        
        current_time = time.time()
        if not force and (current_time - self.last_flush) < self.flush_interval:
            return True, 0
        
        try:
            # Get metrics to process
            metrics_to_process = []
            with self.queue_lock:
                if not self.metrics_queue:
                    return True, 0
                
                # Take up to max_batch_size metrics
                batch_size = min(len(self.metrics_queue), self.max_batch_size)
                for _ in range(batch_size):
                    metrics_to_process.append(self.metrics_queue.popleft())
            
            if not metrics_to_process:
                return True, 0
            
            # Check rate limiting
            if not self._check_rate_limit():
                # Put metrics back in queue
                with self.queue_lock:
                    for metric in reversed(metrics_to_process):
                        self.metrics_queue.appendleft(metric)
                self.stats['rate_limits'] += 1
                return False, 0
            
            # Aggregate metrics by namespace
            batches = self._create_batches(metrics_to_process)
            
            # Send batches
            total_sent = 0
            for batch in batches:
                if self._send_batch(batch):
                    total_sent += len(batch.metrics)
                    self.stats['batches_sent'] += 1
                else:
                    # Put failed metrics back in queue
                    with self.queue_lock:
                        for metric_data in batch.metrics:
                            if len(self.metrics_queue) < self.max_queue_size:
                                # Reconstruct metric from CloudWatch format
                                metric = self._reconstruct_metric(metric_data)
                                self.metrics_queue.append(metric)
            
            self.stats['metrics_sent'] += total_sent
            self.last_flush = current_time
            
            return total_sent > 0, total_sent
            
        except Exception as e:
            logger.warning(f"Failed to flush metrics: {e}")
            self._handle_error()
            return False, 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        with self.queue_lock:
            queue_size = len(self.metrics_queue)
        
        return {
            **self.stats,
            'queue_size': queue_size,
            'circuit_open': self.circuit_open,
            'processing_thread_alive': self.processing_thread.is_alive() if self.processing_thread else False,
            'last_flush': self.last_flush,
            'error_rate': self.stats['errors'] / max(self.stats['metrics_collected'], 1)
        }
    
    def _background_processor(self):
        """Background thread for processing metrics."""
        logger.info("Background metrics processor started")
        
        while not self.stop_processing.is_set():
            try:
                # Process metrics every flush_interval seconds
                if self.stop_processing.wait(self.flush_interval):
                    break
                
                success, sent = self.flush_metrics()
                if sent > 0:
                    logger.debug(f"Background processor sent {sent} metrics")
                
            except Exception as e:
                logger.warning(f"Error in background processor: {e}")
                self._handle_error()
        
        # Final flush on shutdown
        try:
            success, sent = self.flush_metrics(force=True)
            if sent > 0:
                logger.info(f"Final flush sent {sent} metrics")
        except Exception as e:
            logger.warning(f"Error in final flush: {e}")
        
        logger.info("Background metrics processor stopped")
    
    def _create_batches(self, metrics: List[Dict[str, Any]]) -> List[MetricBatch]:
        """Create batches of metrics grouped by namespace."""
        batches_by_namespace = defaultdict(list)
        
        # Group by namespace
        for metric in metrics:
            namespace = metric['namespace']
            
            # Convert to CloudWatch format
            cloudwatch_metric = {
                'MetricName': metric['metric_name'],
                'Value': metric['value'],
                'Unit': metric['unit'],
                'Timestamp': metric['timestamp'],
                'Dimensions': [
                    {'Name': k, 'Value': v} for k, v in metric['dimensions'].items()
                ]
            }
            
            batches_by_namespace[namespace].append(cloudwatch_metric)
        
        # Create batch objects
        batches = []
        for namespace, namespace_metrics in batches_by_namespace.items():
            # Split large namespaces into multiple batches
            for i in range(0, len(namespace_metrics), self.max_batch_size):
                batch_metrics = namespace_metrics[i:i + self.max_batch_size]
                batch = MetricBatch(
                    namespace=namespace,
                    metrics=batch_metrics,
                    timestamp=datetime.now(timezone.utc),
                    batch_id=f"{namespace}_{int(time.time())}_{i}"
                )
                batches.append(batch)
        
        return batches
    
    def _send_batch(self, batch: MetricBatch) -> bool:
        """Send a batch of metrics to CloudWatch."""
        try:
            # Import here to avoid circular imports
            from .aws_utils import get_cloudwatch_client
            
            cloudwatch_client = get_cloudwatch_client(enable_signing=True)
            
            cloudwatch_client.put_metric_data(
                Namespace=batch.namespace,
                MetricData=batch.metrics
            )
            
            # Record successful request
            self.request_timestamps.append(time.time())
            
            logger.debug(f"Sent batch {batch.batch_id} with {len(batch.metrics)} metrics")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to send batch {batch.batch_id}: {e}")
            self._handle_error()
            return False
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        current_time = time.time()
        
        # Remove timestamps older than 1 minute
        while self.request_timestamps and (current_time - self.request_timestamps[0]) > 60:
            self.request_timestamps.popleft()
        
        # Check if we can make another request
        return len(self.request_timestamps) < self.max_requests_per_minute
    
    def _handle_error(self):
        """Handle errors and circuit breaker logic."""
        self.error_count += 1
        self.stats['errors'] += 1
        
        if self.error_count >= self.max_errors:
            self._open_circuit_breaker()
    
    def _open_circuit_breaker(self):
        """Open circuit breaker to prevent cascading failures."""
        self.circuit_open = True
        self.circuit_reset_time = time.time() + self.circuit_timeout
        self.stats['circuit_breaks'] += 1
        logger.warning(f"Circuit breaker opened for {self.circuit_timeout} seconds")
    
    def _reset_circuit_breaker(self):
        """Reset circuit breaker."""
        self.circuit_open = False
        self.error_count = 0
        logger.info("Circuit breaker reset")
    
    def _reconstruct_metric(self, cloudwatch_metric: Dict[str, Any]) -> Dict[str, Any]:
        """Reconstruct internal metric format from CloudWatch format."""
        dimensions = {}
        for dim in cloudwatch_metric.get('Dimensions', []):
            dimensions[dim['Name']] = dim['Value']
        
        return {
            'namespace': 'Chatbot/Costs',  # Default namespace
            'metric_name': cloudwatch_metric['MetricName'],
            'value': cloudwatch_metric['Value'],
            'unit': cloudwatch_metric['Unit'],
            'dimensions': dimensions,
            'timestamp': cloudwatch_metric['Timestamp'],
            'metadata': {}
        }


# Global metrics collector instance
_metrics_collector = None
_collector_lock = threading.Lock()


def get_metrics_collector(config: Optional[Dict[str, Any]] = None) -> MetricsCollector:
    """Get global metrics collector instance."""
    global _metrics_collector
    
    if _metrics_collector is None:
        with _collector_lock:
            if _metrics_collector is None:
                _metrics_collector = MetricsCollector(config)
    
    return _metrics_collector


def collect_metric(namespace: str, metric_name: str, value: float, unit: str, dimensions: Dict[str, str], **kwargs) -> bool:
    """Collect a metric using the global collector."""
    return get_metrics_collector().collect_metric(namespace, metric_name, value, unit, dimensions, **kwargs)


def flush_all_metrics(force: bool = False) -> Tuple[bool, int]:
    """Flush all metrics using the global collector."""
    return get_metrics_collector().flush_metrics(force)


def get_collector_stats() -> Dict[str, Any]:
    """Get collector statistics."""
    return get_metrics_collector().get_stats()
