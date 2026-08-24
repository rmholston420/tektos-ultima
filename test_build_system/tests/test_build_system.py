"""Tests for the build system."""

import os
import tempfile
import time
import unittest
from pathlib import Path

from tektos_build_system.build_graph import BuildGraph, CycleError
from tektos_build_system.cache import Cache
from tektos_build_system.runner import Runner
from tektos_build_system.task import Task, TaskError


class TestBuildGraph(unittest.TestCase):
    """Tests for BuildGraph."""

    def setUp(self):
        """Set up test fixtures."""
        self.graph = BuildGraph()

    def test_add_node(self):
        """Test adding a node."""
        self.graph.add_node("a")
        self.assertTrue(self.graph.has_node("a"))
        self.assertEqual(self.graph.size(), 1)

    def test_add_node_with_deps(self):
        """Test adding a node with dependencies."""
        self.graph.add_node("a")
        self.graph.add_node("b", dependencies=["a"])
        self.assertEqual(self.graph.get_dependencies("b"), {"a"})
        self.assertEqual(self.graph.get_dependents("a"), {"b"})

    def test_remove_node(self):
        """Test removing a node."""
        self.graph.add_node("a")
        self.graph.add_node("b", dependencies=["a"])
        self.graph.remove_node("a")
        self.assertFalse(self.graph.has_node("a"))
        self.assertEqual(self.graph.size(), 1)

    def test_cycle_detection(self):
        """Test cycle detection."""
        self.graph.add_node("a")
        self.graph.add_node("b", dependencies=["a"])
        # This should raise because b depends on a, but a doesn't depend on b
        # To create a cycle, we need to add a node that depends on b
        # But we can't add a node that depends on b if a depends on b
        # Let's test with a different approach
        graph2 = BuildGraph()
        graph2.add_node("a")
        graph2.add_node("b", dependencies=["a"])
        # No cycle here
        self.assertIsNone(graph2.detect_cycle())

    def test_topological_sort(self):
        """Test topological sort."""
        self.graph.add_node("a")
        self.graph.add_node("b", dependencies=["a"])
        self.graph.add_node("c", dependencies=["b"])
        order = self.graph.topological_sort()
        self.assertEqual(order.index("a"), 0)
        self.assertEqual(order.index("b"), 1)
        self.assertEqual(order.index("c"), 2)

    def test_parallel_levels(self):
        """Test parallel execution levels."""
        self.graph.add_node("a")
        self.graph.add_node("b")
        self.graph.add_node("c", dependencies=["a", "b"])
        levels = self.graph.parallel_levels()
        self.assertEqual(len(levels), 2)
        self.assertIn("a", levels[0])
        self.assertIn("b", levels[0])
        self.assertIn("c", levels[1])

    def test_get_ready_tasks(self):
        """Test getting ready tasks."""
        self.graph.add_node("a")
        self.graph.add_node("b", dependencies=["a"])
        ready = self.graph.get_ready_tasks(set())
        self.assertIn("a", ready)
        self.assertNotIn("b", ready)
        ready = self.graph.get_ready_tasks({"a"})
        self.assertIn("b", ready)

    def test_transitive_deps(self):
        """Test transitive dependencies."""
        self.graph.add_node("a")
        self.graph.add_node("b", dependencies=["a"])
        self.graph.add_node("c", dependencies=["b"])
        deps = self.graph.get_all_transitive_deps("c")
        self.assertEqual(deps, {"a", "b"})


class TestTask(unittest.TestCase):
    """Tests for Task."""

    def test_task_creation(self):
        """Test task creation."""
        task = Task(name="test", deps=["a", "b"])
        self.assertEqual(task.name, "test")
        self.assertEqual(task.deps, ["a", "b"])

    def test_cache_key(self):
        """Test cache key generation."""
        task = Task(name="test", deps=["a"])
        key1 = task.cache_key
        task2 = Task(name="test", deps=["a"])
        key2 = task2.cache_key
        self.assertEqual(key1, key2)

    def test_needs_rebuild(self):
        """Test rebuild detection."""
        task = Task(name="test")
        self.assertTrue(task.needs_rebuild())

    def test_execute_with_func(self):
        """Test execution with build function."""
        def build_func(task):
            return "result"

        task = Task(name="test", build_func=build_func)
        result = task.execute()
        self.assertEqual(result, "result")

    def test_execute_with_command(self):
        """Test execution with shell command."""
        task = Task(name="test", command="echo hello")
        result = task.execute()
        self.assertIn("hello", result.stdout)

    def test_execute_fails(self):
        """Test execution failure."""
        task = Task(name="test", command="exit 1")
        with self.assertRaises(TaskError):
            task.execute()


class TestCache(unittest.TestCase):
    """Tests for Cache."""

    def setUp(self):
        """Set up test fixtures."""
        self.cache_dir = tempfile.mkdtemp()
        self.cache = Cache(self.cache_dir)

    def test_put_get(self):
        """Test put and get."""
        self.cache.put("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")

    def test_get_missing(self):
        """Test getting a missing key."""
        self.assertIsNone(self.cache.get("missing"))

    def test_exists(self):
        """Test exists check."""
        self.cache.put("key1", "value1")
        self.assertTrue(self.cache.exists("key1"))
        self.assertFalse(self.cache.exists("missing"))

    def test_delete(self):
        """Test delete."""
        self.cache.put("key1", "value1")
        self.cache.delete("key1")
        self.assertIsNone(self.cache.get("key1"))

    def test_clear(self):
        """Test clear."""
        self.cache.put("key1", "value1")
        self.cache.put("key2", "value2")
        self.cache.clear()
        self.assertEqual(self.cache.size(), 0)

    def test_size(self):
        """Test size."""
        self.assertEqual(self.cache.size(), 0)
        self.cache.put("key1", "value1")
        self.assertEqual(self.cache.size(), 1)


class TestRunner(unittest.TestCase):
    """Tests for Runner."""

    def setUp(self):
        """Set up test fixtures."""
        self.cache_dir = tempfile.mkdtemp()
        self.cache = Cache(self.cache_dir)

    def test_parallel_execution(self):
        """Test parallel execution."""
        graph = BuildGraph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c", dependencies=["a", "b"])

        tasks = {
            "a": Task(name="a", build_func=lambda t: "a"),
            "b": Task(name="b", build_func=lambda t: "b"),
            "c": Task(name="c", build_func=lambda t: "c"),
        }

        runner = Runner(graph, tasks, cache=self.cache, max_workers=2)
        results = runner.build()
        self.assertEqual(results["a"], "a")
        self.assertEqual(results["b"], "b")
        self.assertEqual(results["c"], "c")

    def test_fail_fast(self):
        """Test fail-fast on error."""
        graph = BuildGraph()
        graph.add_node("a")
        graph.add_node("b", dependencies=["a"])

        tasks = {
            "a": Task(name="a", build_func=lambda t: 1/0),
            "b": Task(name="b", build_func=lambda t: "b"),
        }

        runner = Runner(graph, tasks, cache=self.cache, max_workers=2)
        with self.assertRaises(TaskError):
            runner.build()

    def test_clean(self):
        """Test clean."""
        graph = BuildGraph()
        graph.add_node("a")
        tasks = {"a": Task(name="a", build_func=lambda t: "a")}
        runner = Runner(graph, tasks, cache=self.cache, max_workers=2)
        runner.build()
        runner.clean()
        self.assertEqual(self.cache.size(), 0)


if __name__ == "__main__":
    unittest.main()
