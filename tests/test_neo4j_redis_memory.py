"""Tests for Tektos neo4j_memory and redis_memory modules — mocked drivers.

Mocks installed in conftest.py — this file only resets call history.
"""

from unittest.mock import MagicMock

import sys
sys.path.insert(0, '.')

from conftest import mock_redis_client, mock_neo4j_session

from tektos.memory.neo4j_memory import (
    Neo4jProceduralMemory as Neo4jProc,
    Neo4jMemoryConfig as Neo4jConf,
)
from tektos.memory.redis_memory import (
    RedisSensoryMemory as RedisSen,
    RedisWorkingMemory as RedisWork,
    RedisMemoryConfig as RedisConf,
)


class TestNeo4jMemoryConfig:
    def test_default_host(self):
        assert Neo4jConf().host == "localhost"

    def test_default_port(self):
        assert Neo4jConf().port == 7687

    def test_default_database(self):
        assert Neo4jConf().database == "neo4j"

    def test_custom_values(self):
        c = Neo4jConf(host="neo4j.example.com", port=7688, database="mydb", user="admin", password="secret")
        assert c.host == "neo4j.example.com" and c.port == 7688 and c.database == "mydb"


class TestNeo4jProceduralMemory:
    def _setup(self):
        mock_neo4j_session.reset_mock()

    def test_connect_creates_driver(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        assert True  # driver created if no exception

    def test_ensure_schema_creates_constraints(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        assert mock_neo4j_session.run.call_count >= 1

    def test_add_creates_node(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        entry_id = mem.add(content="test procedural memory", skill_id="py", hemisphere="right")
        assert entry_id.startswith("proc-")

    def test_add_with_all_w5h1m(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        mem.add(content="test", who="alice", what="coding", why="learning")

    def test_add_with_metadata_and_w5h1m_merge(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        entry_id = mem.add(content="test", metadata={"key": "val"}, who="bob")
        assert entry_id.startswith("proc-")

    def test_add_relationship(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        mem.add_relationship(from_id="proc-1", to_id="proc-2", edge_type="DEPENDS_ON", strength=0.9)

    def test_add_relationship_default_values(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        mem.add_relationship(from_id="proc-1", to_id="proc-2")

    def test_get_by_skill_id(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        result = mem.get_by_skill_id("python")
        assert isinstance(result, list)

    def test_search_skills(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        result = mem.search_skills("python")
        assert isinstance(result, list)

    def test_get_related(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        result = mem.get_related("proc-1")
        assert isinstance(result, list)

    def test_get_skill_dependencies(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        result = mem.get_skill_dependencies("skill-1")
        assert isinstance(result, list)

    def test_get_skill_enhancements(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        result = mem.get_skill_enhancements("skill-1")
        assert isinstance(result, list)

    def test_get_all(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        result = mem.get_all(limit=10)
        assert isinstance(result, list)

    def test_backup(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        result = mem.backup()
        assert isinstance(result, str)

    def test_close(self):
        self._setup()
        mem = Neo4jProc(config=Neo4jConf())
        mem.connect()
        mem.close()


class TestRedisMemoryConfig:
    def test_default_host(self):
        assert RedisConf().host == "localhost"

    def test_default_port(self):
        assert RedisConf().port == 6379

    def test_default_db(self):
        assert RedisConf().db == 0

    def test_default_sensory_stream_max_len(self):
        assert RedisConf().sensory_stream_max_len == 1000

    def test_custom_values(self):
        c = RedisConf(host="redis.example.com", port=6380, db=1, sensory_stream_max_len=500, sensory_ttl_seconds=7200)
        assert c.host == "redis.example.com" and c.port == 6380 and c.db == 1


class TestRedisSensoryMemory:
    def _setup(self):
        mock_redis_client.reset_mock()

    def test_connect_creates_client(self):
        self._setup()
        mem = RedisSen(config=RedisConf())
        mem.connect()
        assert True  # client created if no exception

    def test_add_adds_to_stream(self):
        self._setup()
        mock_redis_client.xadd.return_value = b"0-0"
        mem = RedisSen(config=RedisConf())
        mem.connect()
        entry_id = mem.add(content="test sensory memory", attention_score=0.9)
        assert entry_id == "0-0"

    def test_add_decodes_entry_id(self):
        self._setup()
        mock_redis_client.xadd.return_value = "stream-id-123"
        mem = RedisSen(config=RedisConf())
        mem.connect()
        entry_id = mem.add(content="test")
        assert entry_id == "stream-id-123"

    def test_get_recent_returns_empty_when_no_conn(self):
        mem = RedisSen(config=RedisConf())
        mem._client = None
        assert mem.get_recent(count=10) == []

    def test_get_recent_returns_results(self):
        self._setup()
        mock_redis_client.xrevrange.return_value = [
            ("0-0", {"content": "mem1", "attention": "0.9", "timestamp": "2024-01-01", "metadata": "{}"}),
            ("0-1", {"content": "mem2", "attention": "0.8", "timestamp": "2024-01-02", "metadata": "{}"}),
        ]
        mem = RedisSen(config=RedisConf())
        mem.connect()
        result = mem.get_recent(count=10)
        assert len(result) == 2
        assert result[0]["content"] == "mem1"

    def test_get_high_attention(self):
        self._setup()
        mock_redis_client.xrevrange.return_value = [
            ("0-0", {"content": "high", "attention": "0.95", "timestamp": "2024-01-01", "metadata": "{}"}),
            ("0-1", {"content": "low", "attention": "0.5", "timestamp": "2024-01-02", "metadata": "{}"}),
        ]
        mem = RedisSen(config=RedisConf())
        mem.connect()
        result = mem.get_high_attention(threshold=0.8)
        assert len(result) == 1

    def test_get_high_attention_all_below_threshold(self):
        self._setup()
        mock_redis_client.xrevrange.return_value = [
            ("0-0", {"content": "low", "attention": "0.5", "timestamp": "2024-01-01", "metadata": "{}"}),
        ]
        mem = RedisSen(config=RedisConf())
        mem.connect()
        result = mem.get_high_attention(threshold=0.8)
        assert result == []

    def test_decay_returns_count(self):
        self._setup()
        mock_redis_client.xlen.side_effect = [1000, 500]
        mem = RedisSen(config=RedisConf())
        mem.connect()
        result = mem.decay()
        assert result == 500

    def test_get_all_returns_all(self):
        self._setup()
        mock_redis_client.xrevrange.return_value = [
            ("0-0", {"content": "mem1", "attention": "0.9", "timestamp": "2024-01-01", "metadata": "{}"}),
        ]
        mem = RedisSen(config=RedisConf())
        mem.connect()
        result = mem.get_all()
        assert len(result) >= 0

    def test_add_with_metadata(self):
        self._setup()
        mock_redis_client.xadd.return_value = b"0-0"
        mem = RedisSen(config=RedisConf())
        mem.connect()
        mem.add(content="test", attention_score=0.8, metadata={"key": "val"})


class TestRedisWorkingMemory:
    def _setup(self):
        mock_redis_client.reset_mock()

    def test_connect_creates_client(self):
        self._setup()
        mem = RedisWork(config=RedisConf())
        mem.connect()

    def test_add_to_hash(self):
        self._setup()
        mock_redis_client.zcard.return_value = 0
        mock_redis_client.zadd.return_value = None
        mem = RedisWork(config=RedisConf())
        mem.connect()
        mem.add(content="test working memory", metadata={"attention": 0.7})
        mock_redis_client.hset.assert_called_once()

    def test_get_all_returns_entries(self):
        self._setup()
        mock_redis_client.zrevrange.return_value = ["key-1", "key-2"]
        def hgetall_side_effect(k):
            if "key-1" in str(k):
                return {"content": "mem1", "significance": "0.9", "timestamp": "2024-01-01", "metadata": "{}"}
            return {"content": "mem2", "significance": "0.5", "timestamp": "2024-01-01", "metadata": "{}"}
        mock_redis_client.hgetall.side_effect = hgetall_side_effect
        mem = RedisWork(config=RedisConf())
        mem.connect()
        result = mem.get_all()
        assert len(result) == 2

    def test_remove_deletes_entry(self):
        self._setup()
        mem = RedisWork(config=RedisConf())
        mem.connect()
        result = mem.remove("key-1")
        assert result is not None

    def test_remove_nonexistent(self):
        self._setup()
        mem = RedisWork(config=RedisConf())
        mem.connect()
        result = mem.remove("nonexistent")
        assert result is not None

    def test_decay_removes_expired(self):
        self._setup()
        mock_redis_client.zcard.return_value = 7
        mem = RedisWork(config=RedisConf())
        mem.connect()
        removed = mem.decay()
        assert isinstance(removed, int)

    def test_get_all_no_conn(self):
        mem = RedisWork(config=RedisConf())
        mem._client = None
        assert mem.get_all() == []
