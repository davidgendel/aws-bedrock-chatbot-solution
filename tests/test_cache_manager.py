"""
Tests for the unified cache manager.
"""
import pytest
import time
from unittest.mock import patch

from src.backend.cache_manager import CacheManager, CacheType, cache_manager


class TestCacheManager:
    """Test cases for CacheManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache_mgr = CacheManager()
    
    def test_cache_basic_operations(self):
        """Test basic cache operations."""
        # Test setting and getting
        assert self.cache_mgr.set(CacheType.RESPONSE, "test_key", "test_value")
        assert self.cache_mgr.get(CacheType.RESPONSE, "test_key") == "test_value"
        
        # Test cache miss
        assert self.cache_mgr.get(CacheType.RESPONSE, "nonexistent_key") is None
    
    def test_cache_types_isolation(self):
        """Test that different cache types are isolated."""
        # Set same key in different cache types
        self.cache_mgr.set(CacheType.RESPONSE, "same_key", "response_value")
        self.cache_mgr.set(CacheType.VECTOR_QUERY, "same_key", "vector_value")
        
        # Verify isolation
        assert self.cache_mgr.get(CacheType.RESPONSE, "same_key") == "response_value"
        assert self.cache_mgr.get(CacheType.VECTOR_QUERY, "same_key") == "vector_value"
    
    def test_sensitive_data_blocking(self):
        """Test that sensitive data is not cached."""
        sensitive_keys = [
            "user_password",
            "api_secret_key",
            "credential_token",
            "private_data",
            "confidential_info"
        ]
        
        for key in sensitive_keys:
            # Should return False (not cached)
            assert not self.cache_mgr.set(CacheType.RESPONSE, key, "sensitive_value")
            # Should return None (not found)
            assert self.cache_mgr.get(CacheType.RESPONSE, key) is None
    
    def test_cache_key_generation(self):
        """Test cache key generation with different data types."""
        # String key
        key1 = self.cache_mgr._generate_cache_key(CacheType.RESPONSE, "string_key")
        assert key1.startswith("response:")
        
        # Dict key
        dict_key = {"param1": "value1", "param2": "value2"}
        key2 = self.cache_mgr._generate_cache_key(CacheType.RESPONSE, dict_key)
        assert key2.startswith("response:")
        
        # List key
        list_key = ["item1", "item2", "item3"]
        key3 = self.cache_mgr._generate_cache_key(CacheType.RESPONSE, list_key)
        assert key3.startswith("response:")
        
        # Same dict in different order should generate same key
        dict_key_reordered = {"param2": "value2", "param1": "value1"}
        key4 = self.cache_mgr._generate_cache_key(CacheType.RESPONSE, dict_key_reordered)
        assert key2 == key4
    
    def test_cache_deletion(self):
        """Test cache deletion."""
        # Set a value
        self.cache_mgr.set(CacheType.RESPONSE, "delete_test", "value")
        assert self.cache_mgr.get(CacheType.RESPONSE, "delete_test") == "value"
        
        # Delete the value
        assert self.cache_mgr.delete(CacheType.RESPONSE, "delete_test")
        assert self.cache_mgr.get(CacheType.RESPONSE, "delete_test") is None
        
        # Try to delete non-existent key
        assert not self.cache_mgr.delete(CacheType.RESPONSE, "nonexistent")
    
    def test_cache_clear(self):
        """Test cache clearing."""
        # Set values in different caches
        self.cache_mgr.set(CacheType.RESPONSE, "key1", "value1")
        self.cache_mgr.set(CacheType.VECTOR_QUERY, "key2", "value2")
        
        # Clear specific cache
        assert self.cache_mgr.clear(CacheType.RESPONSE)
        assert self.cache_mgr.get(CacheType.RESPONSE, "key1") is None
        assert self.cache_mgr.get(CacheType.VECTOR_QUERY, "key2") == "value2"
        
        # Clear all caches
        assert self.cache_mgr.clear()
        assert self.cache_mgr.get(CacheType.VECTOR_QUERY, "key2") is None
    
    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        # Initial stats should be zero
        stats = self.cache_mgr.get_stats()
        assert stats[CacheType.RESPONSE.value]["hits"] == 0
        assert stats[CacheType.RESPONSE.value]["misses"] == 0
        
        # Cache miss should increment misses
        self.cache_mgr.get(CacheType.RESPONSE, "nonexistent")
        stats = self.cache_mgr.get_stats()
        assert stats[CacheType.RESPONSE.value]["misses"] == 1
        
        # Cache hit should increment hits
        self.cache_mgr.set(CacheType.RESPONSE, "test", "value")
        self.cache_mgr.get(CacheType.RESPONSE, "test")
        stats = self.cache_mgr.get_stats()
        assert stats[CacheType.RESPONSE.value]["hits"] == 1
    
    def test_cache_sizes(self):
        """Test cache size tracking."""
        # Initial sizes should be zero
        sizes = self.cache_mgr.get_cache_sizes()
        assert sizes[CacheType.RESPONSE.value] == 0
        
        # Add items and check size
        self.cache_mgr.set(CacheType.RESPONSE, "key1", "value1")
        self.cache_mgr.set(CacheType.RESPONSE, "key2", "value2")
        sizes = self.cache_mgr.get_cache_sizes()
        assert sizes[CacheType.RESPONSE.value] == 2
    
    def test_convenience_functions(self):
        """Test convenience functions for backward compatibility."""
        from src.backend.cache_manager import (
            get_cached_response, cache_response,
            get_cached_vector_query, cache_vector_query,
            get_cached_embedding, cache_embedding,
            clear_all_caches, get_cache_stats
        )
        
        # Test response caching
        assert cache_response("test_message", "test_response")
        assert get_cached_response("test_message") == "test_response"
        
        # Test vector query caching
        query_data = {"query": "test", "limit": 5}
        results = [{"doc": "result1"}, {"doc": "result2"}]
        assert cache_vector_query(query_data, results)
        assert get_cached_vector_query(query_data) == results
        
        # Test embedding caching
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        assert cache_embedding("test_text", embedding)
        assert get_cached_embedding("test_text") == embedding
        
        # Test clear all
        assert clear_all_caches()
        assert get_cached_response("test_message") is None
        
        # Test stats function
        stats = get_cache_stats()
        assert isinstance(stats, dict)
    
    def test_error_handling(self):
        """Test error handling in cache operations."""
        # Test with invalid cache type (should be handled gracefully)
        with patch.object(self.cache_mgr, '_get_cache_and_lock', side_effect=Exception("Test error")):
            assert self.cache_mgr.get(CacheType.RESPONSE, "test") is None
            assert not self.cache_mgr.set(CacheType.RESPONSE, "test", "value")
            assert not self.cache_mgr.delete(CacheType.RESPONSE, "test")
    
    def test_thread_safety(self):
        """Test thread safety of cache operations."""
        import threading
        import time
        
        results = []
        errors = []
        
        def cache_worker(worker_id):
            try:
                for i in range(10):
                    key = f"worker_{worker_id}_item_{i}"
                    value = f"value_{worker_id}_{i}"
                    
                    # Set value
                    self.cache_mgr.set(CacheType.RESPONSE, key, value)
                    
                    # Get value
                    retrieved = self.cache_mgr.get(CacheType.RESPONSE, key)
                    if retrieved == value:
                        results.append(f"worker_{worker_id}_success_{i}")
                    
                    time.sleep(0.001)  # Small delay to increase chance of race conditions
            except Exception as e:
                errors.append(f"worker_{worker_id}_error: {e}")
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=cache_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 50  # 5 workers * 10 items each


class TestGlobalCacheManager:
    """Test the global cache manager instance."""
    
    def test_global_instance(self):
        """Test that global cache manager works correctly."""
        # Test that it's a singleton-like behavior
        assert cache_manager is not None
        assert isinstance(cache_manager, CacheManager)
        
        # Test basic operations on global instance
        cache_manager.set(CacheType.RESPONSE, "global_test", "global_value")
        assert cache_manager.get(CacheType.RESPONSE, "global_test") == "global_value"
        
        # Clean up
        cache_manager.clear()


if __name__ == "__main__":
    pytest.main([__file__])
