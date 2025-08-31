"""
Centralized cost monitoring and metrics collection for the RAG chatbot.
"""
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

try:
    from .aws_utils import get_cloudwatch_client
    from .error_handler import handle_error
except ImportError:
    from aws_utils import get_cloudwatch_client
    from error_handler import handle_error

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of cost metrics."""
    TOKEN_USAGE = "TokenUsage"
    VECTOR_QUERY = "VectorQuery"
    CACHE_HIT = "CacheHit"
    CACHE_MISS = "CacheMiss"
    API_CALL = "APICall"
    STORAGE_OPERATION = "StorageOperation"
    CONVERSATION_COST = "ConversationCost"
    EMBEDDING_GENERATION = "EmbeddingGeneration"
    GUARDRAIL_CHECK = "GuardrailCheck"


@dataclass
class CostMetric:
    """Cost metric data structure."""
    metric_type: MetricType
    value: float
    unit: str
    timestamp: datetime
    dimensions: Dict[str, str]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TokenUsage:
    """Token usage tracking."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model_id: str = ""
    cached: bool = False
    cost_estimate: float = 0.0


@dataclass
class ConversationCost:
    """Conversation-level cost tracking."""
    conversation_id: str
    total_tokens: int = 0
    vector_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_cost_estimate: float = 0.0
    start_time: datetime = None
    last_activity: datetime = None


class CostMonitor:
    """
    Centralized cost monitoring system.
    
    Features:
    - Token usage tracking from Bedrock responses
    - Vector query cost calculation
    - Cache efficiency metrics
    - CloudWatch metrics publishing
    - Conversation-level cost attribution
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize cost monitor."""
        self.config = config or self._load_default_config()
        self.enabled = self.config.get('enabled', True)
        
        if not self.enabled:
            logger.info("Cost monitoring disabled")
            return
        
        # CloudWatch configuration
        self.namespace = self.config.get('cloudWatchNamespace', 'Chatbot/Costs')
        self.batch_size = self.config.get('batchSize', 20)
        self.flush_interval = self.config.get('flushInterval', 60)
        
        # Metrics collection
        self.metrics_queue = []
        self.metrics_lock = threading.RLock()
        self.last_flush = time.time()
        
        # Conversation tracking
        self.conversations = {}
        self.conversations_lock = threading.RLock()
        
        # Cost calculation constants (AWS pricing as of 2024)
        self.pricing = {
            'amazon.nova-lite-v1': {
                'input_tokens_per_1k': 0.00006,  # $0.00006 per 1K input tokens
                'output_tokens_per_1k': 0.00024,  # $0.00024 per 1K output tokens
            },
            'amazon.titan-embed-text-v1': {
                'input_tokens_per_1k': 0.0001,  # $0.0001 per 1K tokens
            },
            's3_vectors': {
                'query_cost': 0.0004,  # $0.0004 per query
                'storage_gb_month': 0.023,  # $0.023 per GB per month
            },
            'lambda': {
                'request_cost': 0.0000002,  # $0.0000002 per request
                'gb_second': 0.0000166667,  # $0.0000166667 per GB-second
            }
        }
        
        # Initialize CloudWatch client
        try:
            self.cloudwatch_client = get_cloudwatch_client()
            logger.info("Cost monitor initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize CloudWatch client: {e}")
            self.cloudwatch_client = None
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default cost monitoring configuration."""
        return {
            'enabled': True,
            'cloudWatchNamespace': 'Chatbot/Costs',
            'batchSize': 20,
            'flushInterval': 60,
            'trackConversationCosts': True,
            'enableDetailedMetrics': True
        }
    
    def track_token_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        model_id: str,
        conversation_id: Optional[str] = None,
        cached: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TokenUsage:
        """
        Track token usage and calculate costs.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model_id: Model identifier
            conversation_id: Optional conversation ID
            cached: Whether response was cached
            metadata: Additional metadata
            
        Returns:
            TokenUsage object with cost calculations
        """
        if not self.enabled:
            return TokenUsage()
        
        try:
            total_tokens = input_tokens + output_tokens
            cost_estimate = self._calculate_token_cost(input_tokens, output_tokens, model_id)
            
            # Create token usage object
            token_usage = TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                model_id=model_id,
                cached=cached,
                cost_estimate=cost_estimate
            )
            
            # Add metrics
            dimensions = {
                'ModelId': model_id,
                'Cached': str(cached)
            }
            
            if conversation_id:
                dimensions['ConversationId'] = conversation_id
                self._update_conversation_cost(conversation_id, tokens=total_tokens, cost=cost_estimate)
            
            # Queue metrics
            self._add_metric(MetricType.TOKEN_USAGE, total_tokens, 'Count', dimensions, metadata)
            
            if not cached:  # Only track cost for non-cached responses
                self._add_metric(MetricType.CONVERSATION_COST, cost_estimate, 'USD', dimensions, metadata)
            
            logger.debug(f"Tracked token usage: {total_tokens} tokens, ${cost_estimate:.6f}")
            return token_usage
            
        except Exception as e:
            logger.warning(f"Failed to track token usage: {e}")
            return TokenUsage()
    
    def track_vector_query(
        self,
        query_count: int = 1,
        vectors_searched: int = 0,
        cache_hit: bool = False,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Track vector query operations and costs.
        
        Args:
            query_count: Number of queries performed
            vectors_searched: Number of vectors searched
            cache_hit: Whether query was served from cache
            conversation_id: Optional conversation ID
            metadata: Additional metadata
            
        Returns:
            Estimated cost of vector operations
        """
        if not self.enabled:
            return 0.0
        
        try:
            cost_estimate = query_count * self.pricing['s3_vectors']['query_cost']
            
            dimensions = {
                'CacheHit': str(cache_hit),
                'VectorsSearched': str(vectors_searched)
            }
            
            if conversation_id:
                dimensions['ConversationId'] = conversation_id
                self._update_conversation_cost(conversation_id, vector_queries=query_count, cost=cost_estimate)
            
            # Queue metrics
            metric_type = MetricType.CACHE_HIT if cache_hit else MetricType.VECTOR_QUERY
            self._add_metric(metric_type, query_count, 'Count', dimensions, metadata)
            
            if not cache_hit:
                self._add_metric(MetricType.CONVERSATION_COST, cost_estimate, 'USD', dimensions, metadata)
            
            logger.debug(f"Tracked vector query: {query_count} queries, ${cost_estimate:.6f}")
            return cost_estimate
            
        except Exception as e:
            logger.warning(f"Failed to track vector query: {e}")
            return 0.0
    
    def track_cache_performance(
        self,
        cache_type: str,
        hit: bool,
        conversation_id: Optional[str] = None,
        cost_saved: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Track cache performance metrics.
        
        Args:
            cache_type: Type of cache (response, vector, embedding, etc.)
            hit: Whether it was a cache hit or miss
            conversation_id: Optional conversation ID
            cost_saved: Estimated cost saved by cache hit
            metadata: Additional metadata
        """
        if not self.enabled:
            return
        
        try:
            dimensions = {
                'CacheType': cache_type
            }
            
            if conversation_id:
                dimensions['ConversationId'] = conversation_id
                if hit:
                    self._update_conversation_cost(conversation_id, cache_hits=1)
                else:
                    self._update_conversation_cost(conversation_id, cache_misses=1)
            
            # Queue metrics
            metric_type = MetricType.CACHE_HIT if hit else MetricType.CACHE_MISS
            self._add_metric(metric_type, 1, 'Count', dimensions, metadata)
            
            if hit and cost_saved > 0:
                # Track cost savings from cache hits
                savings_dimensions = dimensions.copy()
                savings_dimensions['Metric'] = 'CostSaved'
                self._add_metric(MetricType.CONVERSATION_COST, -cost_saved, 'USD', savings_dimensions, metadata)
            
            logger.debug(f"Tracked cache {'hit' if hit else 'miss'}: {cache_type}")
            
        except Exception as e:
            logger.warning(f"Failed to track cache performance: {e}")
    
    def track_api_call(
        self,
        api_type: str,
        duration_ms: float = 0,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Track API call metrics.
        
        Args:
            api_type: Type of API call (bedrock, s3, etc.)
            duration_ms: Duration in milliseconds
            conversation_id: Optional conversation ID
            metadata: Additional metadata
        """
        if not self.enabled:
            return
        
        try:
            dimensions = {
                'APIType': api_type
            }
            
            if conversation_id:
                dimensions['ConversationId'] = conversation_id
            
            # Queue metrics
            self._add_metric(MetricType.API_CALL, 1, 'Count', dimensions, metadata)
            
            if duration_ms > 0:
                duration_dimensions = dimensions.copy()
                duration_dimensions['Metric'] = 'Duration'
                self._add_metric(MetricType.API_CALL, duration_ms, 'Milliseconds', duration_dimensions, metadata)
            
            logger.debug(f"Tracked API call: {api_type}, {duration_ms}ms")
            
        except Exception as e:
            logger.warning(f"Failed to track API call: {e}")
    
    def get_conversation_cost(self, conversation_id: str) -> Optional[ConversationCost]:
        """Get cost information for a conversation."""
        if not self.enabled:
            return None
        
        with self.conversations_lock:
            return self.conversations.get(conversation_id)
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get overall cost summary."""
        if not self.enabled:
            return {}
        
        try:
            with self.conversations_lock:
                total_conversations = len(self.conversations)
                total_cost = sum(conv.total_cost_estimate for conv in self.conversations.values())
                total_tokens = sum(conv.total_tokens for conv in self.conversations.values())
                total_vector_queries = sum(conv.vector_queries for conv in self.conversations.values())
                total_cache_hits = sum(conv.cache_hits for conv in self.conversations.values())
                total_cache_misses = sum(conv.cache_misses for conv in self.conversations.values())
            
            cache_hit_rate = 0.0
            if total_cache_hits + total_cache_misses > 0:
                cache_hit_rate = total_cache_hits / (total_cache_hits + total_cache_misses)
            
            return {
                'total_conversations': total_conversations,
                'total_cost_estimate': round(total_cost, 6),
                'total_tokens': total_tokens,
                'total_vector_queries': total_vector_queries,
                'cache_hit_rate': round(cache_hit_rate, 3),
                'average_cost_per_conversation': round(total_cost / total_conversations, 6) if total_conversations > 0 else 0,
                'metrics_queue_size': len(self.metrics_queue)
            }
            
        except Exception as e:
            logger.warning(f"Failed to get cost summary: {e}")
            return {}
    
    def flush_metrics(self, force: bool = False) -> bool:
        """
        Flush metrics to CloudWatch.
        
        Args:
            force: Force flush regardless of timing
            
        Returns:
            True if metrics were flushed successfully
        """
        if not self.enabled or not self.cloudwatch_client:
            return False
        
        current_time = time.time()
        if not force and (current_time - self.last_flush) < self.flush_interval:
            return False
        
        try:
            with self.metrics_lock:
                if not self.metrics_queue:
                    return True
                
                # Prepare metrics for CloudWatch
                metrics_to_send = self.metrics_queue[:self.batch_size]
                self.metrics_queue = self.metrics_queue[self.batch_size:]
            
            # Convert to CloudWatch format
            metric_data = []
            for metric in metrics_to_send:
                metric_data.append({
                    'MetricName': metric.metric_type.value,
                    'Value': metric.value,
                    'Unit': metric.unit,
                    'Timestamp': metric.timestamp,
                    'Dimensions': [
                        {'Name': k, 'Value': v} for k, v in metric.dimensions.items()
                    ]
                })
            
            # Send to CloudWatch
            self.cloudwatch_client.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
            
            self.last_flush = current_time
            logger.debug(f"Flushed {len(metric_data)} metrics to CloudWatch")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to flush metrics to CloudWatch: {e}")
            return False
    
    def _calculate_token_cost(self, input_tokens: int, output_tokens: int, model_id: str) -> float:
        """Calculate cost based on token usage."""
        try:
            # Strip version suffix from model ID (e.g., 'amazon.nova-lite-v1:0' -> 'amazon.nova-lite-v1')
            base_model_id = model_id.split(':')[0]
            model_pricing = self.pricing.get(base_model_id, {})
            
            input_cost = (input_tokens / 1000) * model_pricing.get('input_tokens_per_1k', 0)
            output_cost = (output_tokens / 1000) * model_pricing.get('output_tokens_per_1k', 0)
            
            return input_cost + output_cost
            
        except Exception as e:
            logger.warning(f"Failed to calculate token cost: {e}")
            return 0.0
    
    def _update_conversation_cost(
        self,
        conversation_id: str,
        tokens: int = 0,
        vector_queries: int = 0,
        cache_hits: int = 0,
        cache_misses: int = 0,
        cost: float = 0.0
    ):
        """Update conversation cost tracking."""
        try:
            with self.conversations_lock:
                if conversation_id not in self.conversations:
                    self.conversations[conversation_id] = ConversationCost(
                        conversation_id=conversation_id,
                        start_time=datetime.now(timezone.utc)
                    )
                
                conv = self.conversations[conversation_id]
                conv.total_tokens += tokens
                conv.vector_queries += vector_queries
                conv.cache_hits += cache_hits
                conv.cache_misses += cache_misses
                conv.total_cost_estimate += cost
                conv.last_activity = datetime.now(timezone.utc)
                
        except Exception as e:
            logger.warning(f"Failed to update conversation cost: {e}")
    
    def _add_metric(
        self,
        metric_type: MetricType,
        value: float,
        unit: str,
        dimensions: Dict[str, str],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add metric to queue."""
        try:
            metric = CostMetric(
                metric_type=metric_type,
                value=value,
                unit=unit,
                timestamp=datetime.now(timezone.utc),
                dimensions=dimensions,
                metadata=metadata
            )
            
            with self.metrics_lock:
                self.metrics_queue.append(metric)
                
                # Auto-flush if queue is full
                if len(self.metrics_queue) >= self.batch_size:
                    self.flush_metrics(force=True)
                    
        except Exception as e:
            logger.warning(f"Failed to add metric: {e}")


# Global cost monitor instance
_cost_monitor = None
_monitor_lock = threading.Lock()


def get_cost_monitor(config: Optional[Dict[str, Any]] = None) -> CostMonitor:
    """Get global cost monitor instance."""
    global _cost_monitor
    
    if _cost_monitor is None:
        with _monitor_lock:
            if _cost_monitor is None:
                _cost_monitor = CostMonitor(config)
    
    return _cost_monitor


# Convenience functions
def track_tokens(input_tokens: int, output_tokens: int, model_id: str, **kwargs) -> TokenUsage:
    """Track token usage."""
    return get_cost_monitor().track_token_usage(input_tokens, output_tokens, model_id, **kwargs)


def track_vector_query(query_count: int = 1, **kwargs) -> float:
    """Track vector query."""
    return get_cost_monitor().track_vector_query(query_count, **kwargs)


def track_cache_hit(cache_type: str, **kwargs):
    """Track cache hit."""
    get_cost_monitor().track_cache_performance(cache_type, True, **kwargs)


def track_cache_miss(cache_type: str, **kwargs):
    """Track cache miss."""
    get_cost_monitor().track_cache_performance(cache_type, False, **kwargs)


def flush_cost_metrics(force: bool = False) -> bool:
    """Flush cost metrics to CloudWatch."""
    return get_cost_monitor().flush_metrics(force)


def get_cost_summary() -> Dict[str, Any]:
    """Get cost summary."""
    return get_cost_monitor().get_cost_summary()
