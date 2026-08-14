"""Tests for Redis-backed Sensory and Working Memory tiers.

Tests both the API contract and graceful degradation when Redis is unavailable.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.tektos.memory.redis_memory import (
    RedisMemoryConfig,
    RedisSensoryMemory,
    RedisWorkingMemory,
)


class TestRedisSensoryMemory:
    """Tests for Redis-backed sensory memory."""
    
    def test_config_defaults(self):
        """Test RedisMemoryConfig default values."""
        config = RedisMemoryConfig()
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.sensory_stream_max_len == 1000
        assert config.sensory_ttl_seconds == 4.0
    
    def test_config_custom(self):
        """Test RedisMemoryConfig with custom values."""
        config = RedisMemoryConfig(host="redis.example.com", port=6380, db=1)
        assert config.host == "redis.example.com"
        assert config.port == 6380
        assert config.db == 1
    
    @patch("src.tektos.memory.redis_memory._redis", None)
    def test_redis_not_available(self):
        """Test graceful degradation when redis-py is not installed."""
        import sys
        # Simulate missing redis
        old_modules = {k: v for k, v in sys.modules.items() if "redis" in k}
        for k in old_modules:
            del sys.modules[k]
        
        # Reimport to get REDIS_AVAILABLE=False
        import importlib
        import src.tektos.memory.redis_memory as redis_mod
        importlib.reload(redis_mod)
        
        sensory = redis_mod.RedisSensoryMemory()
        
        with pytest.raises(RuntimeError, match="redis-py not installed"):
            sensory.connect()
    
    def test_sensory_memory_creation(self):
        """Test creating a RedisSensoryMemory instance."""
        sensory = RedisSensoryMemory()
        assert sensory._stream_key == "tektos:sensory:stream"
    
    def test_sensory_memory_custom_config(self):
        """Test creating with custom config."""
        config = RedisMemoryConfig(sensory_key_prefix="custom:sensory")
        sensory = RedisSensoryMemory(config)
        assert sensory._stream_key == "custom:sensory:stream"
    
    @patch("src.tektos.memory.redis_memory._redis", None)
    def test_add_without_connection(self):
        """Test add() raises RuntimeError without connection."""
        import sys
        old_modules = {k: v for k, v in sys.modules.items() if "redis" in k}
        for k in old_modules:
            del sys.modules[k]
        
        import importlib
        import src.tektos.memory.redis_memory as redis_mod
        importlib.reload(redis_mod)
        
        sensory = redis_mod.RedisSensoryMemory()
        
        with pytest.raises(RuntimeError):
            sensory.add("test content")
    
    def test_get_recent_without_connection(self):
        """Test get_recent() returns empty list without connection."""
        sensory = RedisSensoryMemory()
        result = sensory.get_recent()
        assert result == []
    
    def test_get_high_attention_without_connection(self):
        """Test get_high_attention() returns empty list without connection."""
        sensory = RedisSensoryMemory()
        result = sensory.get_high_attention()
        assert result == []
    
    def test_decay_without_connection(self):
        """Test decay() returns 0 without connection."""
        sensory = RedisSensoryMemory()
        result = sensory.decay()
        assert result == 0
    
    def test_get_all_without_connection(self):
        """Test get_all() returns empty list without connection."""
        sensory = RedisSensoryMemory()
        result = sensory.get_all()
        assert result == []
    
    @patch("src.tektos.memory.redis_memory._redis", None)
    def test_sensory_memory_methods_with_mock(self):
        """Test sensory memory methods with mocked Redis client."""
        import sys
        old_modules = {k: v for k, v in sys.modules.items() if "redis" in k}
        for k in old_modules:
            del sys.modules[k]
        
        import importlib
        import src.tektos.memory.redis_memory as redis_mod
        importlib.reload(redis_mod)
        
        sensory = redis_mod.RedisSensoryMemory()
        
        # Mock the Redis client
        mock_client = MagicMock()
        mock_client.xadd.return_value = b"1234567890-0"
        sensory._client = mock_client
        
        # Test add
        entry_id = sensory.add("test content", attention_score=0.9)
        assert entry_id == "1234567890-0"
        mock_client.xadd.assert_called_once()
        mock_client.expire.assert_called_once()
    
    def test_sensory_memory_attention_threshold(self):
        """Test that attention scores are stored correctly."""
        sensory = RedisSensoryMemory()
        
        mock_client = MagicMock()
        mock_client.xadd.return_value = b"1234567890-0"
        sensory._client = mock_client
        
        sensory.add("content", attention_score=0.5)
        
        # xadd uses positional args: xadd(key, fields, ...)
        # Fields dict is the second positional arg
        fields_dict = mock_client.xadd.call_args[0][1]
        assert fields_dict["attention"] == "0.5"
    
    def test_sensory_memory_metadata(self):
        """Test that metadata is stored as JSON."""
        sensory = RedisSensoryMemory()
        
        mock_client = MagicMock()
        mock_client.xadd.return_value = b"1234567890-0"
        sensory._client = mock_client
        
        metadata = {"who": "user", "what": "test_event"}
        sensory.add("content", metadata=metadata)
        
        # Fields dict is the second positional arg
        fields_dict = mock_client.xadd.call_args[0][1]
        assert json.loads(fields_dict["metadata"]) == metadata


class TestRedisWorkingMemory:
    """Tests for Redis-backed working memory."""
    
    def test_config_defaults(self):
        """Test RedisMemoryConfig default values."""
        config = RedisMemoryConfig()
        assert config.working_capacity == 7
        assert config.working_ttl_seconds == 300.0
    
    def test_working_memory_creation(self):
        """Test creating a RedisWorkingMemory instance."""
        working = RedisWorkingMemory()
        assert working._sorted_set_key == "tektos:working:set"
        assert working._hash_prefix == "tektos:working:entry"
    
    def test_working_memory_custom_config(self):
        """Test creating with custom config."""
        config = RedisMemoryConfig(
            working_capacity=9,
            working_ttl_seconds=600.0,
            working_key_prefix="custom:working",
        )
        working = RedisWorkingMemory(config)
        assert working._sorted_set_key == "custom:working:set"
        assert working._hash_prefix == "custom:working:entry"
        assert working.config.working_capacity == 9
        assert working.config.working_ttl_seconds == 600.0
    
    @patch("src.tektos.memory.redis_memory._redis", None)
    def test_working_not_available(self):
        """Test graceful degradation when redis-py is not installed."""
        import sys
        old_modules = {k: v for k, v in sys.modules.items() if "redis" in k}
        for k in old_modules:
            del sys.modules[k]
        
        import importlib
        import src.tektos.memory.redis_memory as redis_mod
        importlib.reload(redis_mod)
        
        working = redis_mod.RedisWorkingMemory()
        
        with pytest.raises(RuntimeError, match="redis-py not installed"):
            working.connect()
    
    def test_get_all_without_connection(self):
        """Test get_all() returns empty list without connection."""
        working = RedisWorkingMemory()
        result = working.get_all()
        assert result == []
    
    def test_remove_without_connection(self):
        """Test remove() returns False without connection."""
        working = RedisWorkingMemory()
        result = working.remove("nonexistent-id")
        assert result is False
    
    def test_decay_without_connection(self):
        """Test decay() returns 0 without connection."""
        working = RedisWorkingMemory()
        result = working.decay()
        assert result == 0
    
    def test_working_memory_add_with_mock(self):
        """Test add() with mocked Redis client."""
        working = RedisWorkingMemory()
        
        mock_client = MagicMock()
        mock_client.zcard.return_value = 0
        working._client = mock_client
        
        entry_id = working.add("test content", significance=0.8)
        
        assert entry_id.startswith("mem-")
        mock_client.zadd.assert_called_once()
        mock_client.hset.assert_called_once()
        mock_client.expire.assert_called_once()
    
    def test_working_memory_capacity_enforcement(self):
        """Test that capacity is enforced on add."""
        working = RedisWorkingMemory()
        
        mock_client = MagicMock()
        mock_client.zcard.return_value = 10  # Over capacity (7)
        # zrange needs to return actual member strings for the loop to work
        mock_client.zrange.return_value = [b"mem-1", b"mem-2", b"mem-3"]
        working._client = mock_client
        
        working.add("new content", significance=0.9)
        
        # Should call zrange to get lowest scoring entries
        mock_client.zrange.assert_called_once()
        mock_client.zrem.assert_called()
        mock_client.delete.assert_called()
    
    def test_working_memory_remove_with_mock(self):
        """Test remove() with mocked Redis client."""
        working = RedisWorkingMemory()
        
        mock_client = MagicMock()
        working._client = mock_client
        
        result = working.remove("mem-test1234")
        
        assert result is True
        mock_client.zrem.assert_called_once_with(working._sorted_set_key, "mem-test1234")
        mock_client.delete.assert_called_once()
    
    def test_working_memory_significance_sorting(self):
        """Test that entries are stored by significance score."""
        working = RedisWorkingMemory()
        
        mock_client = MagicMock()
        mock_client.zcard.return_value = 0
        working._client = mock_client
        
        working.add("low importance", significance=0.1)
        working.add("high importance", significance=0.9)
        working.add("medium importance", significance=0.5)
        
        # zadd should be called 3 times with different scores
        assert mock_client.zadd.call_count == 3
        
        # zadd uses positional args: zadd(key, mapping_dict)
        # mapping dict is the second positional arg
        calls = mock_client.zadd.call_args_list
        mapping_dicts = [call[0][1] for call in calls]
        scores = [list(d.values()) for d in mapping_dicts]
        
        assert 0.1 in scores[0]
        assert 0.9 in scores[1]
        assert 0.5 in scores[2]
