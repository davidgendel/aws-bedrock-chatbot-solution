"""
Unified caching manager for the chatbot RAG solution.
Consolidates all caching strategies into a single, efficient system.
"""
import hashlib
import json
import logging
import time
import threading
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from cachetools import TTLCache, LRUCache

logger = logging.getLogger(__name__)


class CacheType(Enum):
    """Cache types for different data categories."""
    RESPONSE = "response"           # Chat responses
    VECTOR_QUERY = "vector_query"   # Vector similarity queries
    EMBEDDING = "embedding"         # Document embeddings
    METADATA = "metadata"           # Document metadata
    CONFIG = "config"               # Configuration data
    PROMPT = "prompt"               # Bedrock prompt responses
    CONTEXT = "context"             # Retrieved document context
    GUARDRAIL = "guardrail"         # Guardrail results


class CacheManager:
    """Unified cache manager with multiple cache layers."""
    
    def __init__(self):
        """Initialize the cache manager with optimized cache configurations."""
        # Response cache - for chat responses (most frequently accessed)
        self.response_cache = TTLCache(maxsize=500, ttl=7200)  # 2 hours TTL
        self.response_lock = threading.RLock()
        
        # Vector query cache - for similarity search results
        self.vector_cache = TTLCache(maxsize=200, ttl=7200)  # 2 hours TTL
        self.vector_lock = threading.RLock()
        
        # Embedding cache - for document embeddings (less frequently accessed but expensive to compute)
        self.embedding_cache = LRUCache(maxsize=1000)  # LRU for long-term storage
        self.embedding_lock = threading.RLock()
        
        # Metadata cache - for document metadata (small, frequently accessed)
        self.metadata_cache = TTLCache(maxsize=100, ttl=7200)  # 2 hours TTL
        self.metadata_lock = threading.RLock()
        
        # Config cache - for configuration data (rarely changes)
        self.config_cache = TTLCache(maxsize=10, ttl=7200)  # 2 hours TTL
        self.config_lock = threading.RLock()
        
        # Prompt cache - for Bedrock prompt responses
        self.prompt_cache = TTLCache(maxsize=500, ttl=3600)  # 1 hour TTL
        self.prompt_lock = threading.RLock()
        
        # Context cache - for retrieved document context
        self.context_cache = TTLCache(maxsize=300, ttl=3600)  # 1 hour TTL
        self.context_lock = threading.RLock()
        
        # Guardrail cache - for guardrail results
        self.guardrail_cache = TTLCache(maxsize=200, ttl=3600)  # 1 hour TTL
        self.guardrail_lock = threading.RLock()
        
        # Cache statistics
        self.stats = {
            CacheType.RESPONSE: {"hits": 0, "misses": 0},
            CacheType.VECTOR_QUERY: {"hits": 0, "misses": 0},
            CacheType.EMBEDDING: {"hits": 0, "misses": 0},
            CacheType.METADATA: {"hits": 0, "misses": 0},
            CacheType.CONFIG: {"hits": 0, "misses": 0},
            CacheType.PROMPT: {"hits": 0, "misses": 0},
            CacheType.CONTEXT: {"hits": 0, "misses": 0},
            CacheType.GUARDRAIL: {"hits": 0, "misses": 0},
        }
        
        # Sensitive data patterns to never cache (specific patterns for security)
        self.sensitive_patterns = [
            'password', 'secret_key', 'api_key', 'credential', 'private_data',
            'confidential', 'auth_token', 'access_key', 'ssn', 'credit_card'
        ]
    
    def _get_cache_and_lock(self, cache_type: CacheType) -> Tuple[Union[TTLCache, LRUCache], threading.RLock]:
        """Get the appropriate cache and lock for the given cache type."""
        cache_map = {
            CacheType.RESPONSE: (self.response_cache, self.response_lock),
            CacheType.VECTOR_QUERY: (self.vector_cache, self.vector_lock),
            CacheType.EMBEDDING: (self.embedding_cache, self.embedding_lock),
            CacheType.METADATA: (self.metadata_cache, self.metadata_lock),
            CacheType.CONFIG: (self.config_cache, self.config_lock),
            CacheType.PROMPT: (self.prompt_cache, self.prompt_lock),
            CacheType.CONTEXT: (self.context_cache, self.context_lock),
            CacheType.GUARDRAIL: (self.guardrail_cache, self.guardrail_lock),
        }
        return cache_map[cache_type]
    
    def _generate_cache_key(self, cache_type: CacheType, key_data: Union[str, Dict, List]) -> str:
        """Generate a consistent cache key from the input data."""
        # Convert key_data to string if it's not already
        if isinstance(key_data, (dict, list)):
            key_str = json.dumps(key_data, sort_keys=True)
        else:
            key_str = str(key_data)
        
        # Check for sensitive data
        key_lower = key_str.lower()
        if any(pattern in key_lower for pattern in self.sensitive_patterns):
            logger.warning("Attempted to cache sensitive data - blocked")
            return None
        
        # Generate hash-based key with cache type prefix
        hash_obj = hashlib.md5(key_str.encode('utf-8'))
        return f"{cache_type.value}:{hash_obj.hexdigest()}"
    
    def get(self, cache_type: CacheType, key_data: Union[str, Dict, List]) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            cache_type: Type of cache to use
            key_data: Data to generate cache key from
            
        Returns:
            Cached value or None if not found
        """
        try:
            cache_key = self._generate_cache_key(cache_type, key_data)
            if not cache_key:
                return None
            
            cache, lock = self._get_cache_and_lock(cache_type)
            
            with lock:
                value = cache.get(cache_key)
                if value is not None:
                    self.stats[cache_type]["hits"] += 1
                    logger.debug(f"Cache hit for {cache_type.value}")
                    return value
                else:
                    self.stats[cache_type]["misses"] += 1
                    logger.debug(f"Cache miss for {cache_type.value}")
                    return None
        except Exception as e:
            logger.error("Error getting from cache")
            if cache_type in self.stats:
                self.stats[cache_type]["misses"] += 1
            return None
    
    def set(self, cache_type: CacheType, key_data: Union[str, Dict, List], value: Any, ttl_override: Optional[int] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            cache_type: Type of cache to use
            key_data: Data to generate cache key from
            value: Value to cache
            ttl_override: Override TTL for TTL caches (ignored for LRU caches)
            
        Returns:
            True if successfully cached, False otherwise
        """
        try:
            cache_key = self._generate_cache_key(cache_type, key_data)
            if not cache_key:
                return False
            
            cache, lock = self._get_cache_and_lock(cache_type)
            
            with lock:
                # For TTL caches, we can set custom TTL if supported
                if isinstance(cache, TTLCache) and ttl_override:
                    # Note: cachetools doesn't support per-item TTL, so we log the request
                    logger.debug(f"TTL override requested but not supported: {ttl_override}")
                
                cache[cache_key] = value
                logger.debug(f"Cached value for {cache_type.value}")
                return True
        except Exception as e:
            logger.error("Error setting cache")
            return False
            logger.error("Error setting cache")
            return False
    
    def delete(self, cache_type: CacheType, key_data: Union[str, Dict, List]) -> bool:
        """
        Delete value from cache.
        
        Args:
            cache_type: Type of cache to use
            key_data: Data to generate cache key from
            
        Returns:
            True if successfully deleted, False otherwise
        """
        try:
            cache_key = self._generate_cache_key(cache_type, key_data)
            if not cache_key:
                return False
            
            cache, lock = self._get_cache_and_lock(cache_type)
            
            with lock:
                if cache_key in cache:
                    del cache[cache_key]
                    logger.debug(f"Deleted from cache {cache_type.value}")
                    return True
                return False
        except Exception as e:
            logger.error("Error deleting from cache")
            return False
            logger.error("Error deleting from cache")
            return False
    
    def clear(self, cache_type: Optional[CacheType] = None) -> bool:
        """
        Clear cache(s).
        
        Args:
            cache_type: Specific cache type to clear, or None to clear all
            
        Returns:
            True if successfully cleared
        """
        try:
            if cache_type:
                cache, lock = self._get_cache_and_lock(cache_type)
                with lock:
                    cache.clear()
                logger.info(f"Cleared {cache_type.value} cache")
            else:
                # Clear all caches
                for ct in CacheType:
                    cache, lock = self._get_cache_and_lock(ct)
                    with lock:
                        cache.clear()
                logger.info("Cleared all caches")
            
            return True
        except Exception as e:
            logger.error("Error clearing cache")
            return False
    
    def get_stats(self) -> Dict[str, Dict[str, Union[int, float]]]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        stats_with_ratios = {}
        
        for cache_type, stats in self.stats.items():
            hits = stats["hits"]
            misses = stats["misses"]
            total = hits + misses
            hit_ratio = hits / total if total > 0 else 0.0
            
            stats_with_ratios[cache_type.value] = {
                "hits": hits,
                "misses": misses,
                "total": total,
                "hit_ratio": hit_ratio
            }
        
        return stats_with_ratios
    
    def get_cache_sizes(self) -> Dict[str, int]:
        """
        Get current cache sizes.
        
        Returns:
            Dictionary with cache sizes
        """
        sizes = {}
        
        for cache_type in CacheType:
            cache, lock = self._get_cache_and_lock(cache_type)
            with lock:
                sizes[cache_type.value] = len(cache)
        
        return sizes
    
    def cleanup_expired(self) -> Dict[str, int]:
        """
        Force cleanup of expired entries (mainly for TTL caches).
        
        Returns:
            Dictionary with number of entries cleaned per cache
        """
        cleaned = {}
        
        for cache_type in CacheType:
            cache, lock = self._get_cache_and_lock(cache_type)
            
            if isinstance(cache, TTLCache):
                with lock:
                    initial_size = len(cache)
                    # Access a non-existent key to trigger cleanup
                    cache.get("__cleanup_trigger__", None)
                    final_size = len(cache)
                    cleaned[cache_type.value] = initial_size - final_size
            else:
                cleaned[cache_type.value] = 0
        
        return cleaned


# Global cache manager instance
cache_manager = CacheManager()


# Convenience functions for backward compatibility
def get_cached_response(message: str) -> Optional[str]:
    """Get cached chat response."""
    return cache_manager.get(CacheType.RESPONSE, message)


def cache_response(message: str, response: str) -> bool:
    """Cache chat response."""
    return cache_manager.set(CacheType.RESPONSE, message, response)


def get_cached_vector_query(query_data: Dict) -> Optional[List]:
    """Get cached vector query result."""
    return cache_manager.get(CacheType.VECTOR_QUERY, query_data)


def cache_vector_query(query_data: Dict, results: List) -> bool:
    """Cache vector query result."""
    return cache_manager.set(CacheType.VECTOR_QUERY, query_data, results)


def get_cached_embedding(text: str) -> Optional[List[float]]:
    """Get cached embedding."""
    return cache_manager.get(CacheType.EMBEDDING, text)


def cache_embedding(text: str, embedding: List[float]) -> bool:
    """Cache embedding."""
    return cache_manager.set(CacheType.EMBEDDING, text, embedding)


def get_cached_prompt_response(prompt: str) -> Optional[str]:
    """Get cached prompt response."""
    return cache_manager.get(CacheType.PROMPT, prompt)


def cache_prompt_response(prompt: str, response: str) -> bool:
    """Cache prompt response."""
    return cache_manager.set(CacheType.PROMPT, prompt, response)


def get_cached_context(query_key: str) -> Optional[List[Dict[str, Any]]]:
    """Get cached document context."""
    return cache_manager.get(CacheType.CONTEXT, query_key)


def cache_context_data(query_key: str, context: List[Dict[str, Any]]) -> bool:
    """Cache document context."""
    return cache_manager.set(CacheType.CONTEXT, query_key, context)


def get_cached_guardrail_result(text: str) -> Optional[Dict[str, Any]]:
    """Get cached guardrail result."""
    return cache_manager.get(CacheType.GUARDRAIL, text)


def cache_guardrail_result(text: str, result: Dict[str, Any]) -> bool:
    """Cache guardrail result."""
    return cache_manager.set(CacheType.GUARDRAIL, text, result)


def clear_all_caches() -> bool:
    """Clear all caches."""
    return cache_manager.clear()


def get_cache_stats() -> Dict[str, Dict[str, Union[int, float]]]:
    """Get cache statistics."""
    return cache_manager.get_stats()
