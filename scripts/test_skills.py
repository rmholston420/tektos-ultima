#!/usr/bin/env python3
"""Comprehensive test of Tektos skill system.

Tests:
1. Skill listing and stats
2. Skill selection (matching skills to context)
3. Skill execution
4. Skill improvement
5. Deduplication
6. Maintenance
7. Error handling
"""

import json
import sys
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import requests

BASE_URL = "http://localhost:8020"


def test_skill_listing():
    """Test 1: List all skills and verify pre-seed count."""
    print("=" * 60)
    print("TEST 1: Skill Listing")
    print("=" * 60)
    
    resp = requests.get(f"{BASE_URL}/api/skills")
    assert resp.status_code == 200, f"Failed to list skills: {resp.text}"
    
    data = resp.json()
    skills = data.get("skills", [])
    
    print(f"✅ Total skills: {len(skills)}")
    assert len(skills) >= 20, f"Expected at least 20 skills, got {len(skills)}"
    
    # Verify categories
    categories = set(s.get("category") for s in skills)
    print(f"✅ Categories: {sorted(categories)}")
    assert len(categories) >= 15, f"Expected at least 15 categories, got {len(categories)}"
    
    # Verify all skills are active
    active = [s for s in skills if s.get("enabled", True)]
    print(f"✅ Active skills: {len(active)}")
    assert len(active) == len(skills), f"Expected all skills active, got {len(active)}/{len(skills)}"
    
    # Verify preseed source (allow for some test-created skills)
    preseed = [s for s in skills if s.get("source") == "preseed"]
    print(f"✅ Preseed skills: {len(preseed)}")
    assert len(preseed) >= 20, f"Expected at least 20 preseed skills, got {len(preseed)}"
    
    print()


def test_skill_stats():
    """Test 2: Get skill statistics."""
    print("=" * 60)
    print("TEST 2: Skill Statistics")
    print("=" * 60)
    
    resp = requests.get(f"{BASE_URL}/api/skills/stats")
    assert resp.status_code == 200, f"Failed to get stats: {resp.text}"
    
    data = resp.json()
    print(f"✅ Total skills: {data.get('total_skills')}")
    print(f"✅ Active skills: {data.get('active_skills')}")
    print(f"✅ Categories: {len(data.get('categories', []))}")
    
    assert data.get("total_skills") == 23
    assert data.get("active_skills") == 23
    assert len(data.get("categories", [])) == 17
    
    print()


def test_skill_selection():
    """Test 3: Test skill selection with different contexts."""
    print("=" * 60)
    print("TEST 3: Skill Selection")
    print("=" * 60)
    
    # Test context 1: File operations
    context1 = {
        "task": "Read a file and process its contents",
        "task_type": "file_operations",
        "description": "Need to read a configuration file from disk",
    }
    
    resp = requests.post(
        f"{BASE_URL}/api/skills/select",
        json={"context": context1, "max_skills": 5},
    )
    assert resp.status_code == 200, f"Failed to select skills: {resp.text}"
    
    data = resp.json()
    selected = data.get("selected", [])
    print(f"✅ Context 1 (file operations): {len(selected)} skills selected")
    for s in selected:
        print(f"   - {s['name']} (score={s.get('score', 0):.1f})")
    
    # Should select file-related skills
    file_skills = [s for s in selected if s.get("category") == "file_operations"]
    print(f"✅ File operation skills: {len(file_skills)}")
    assert len(file_skills) >= 1, "Should select at least one file operation skill"
    
    # Test context 2: Testing
    context2 = {
        "task": "Write unit tests for the new feature",
        "task_type": "testing",
        "description": "Need to create comprehensive test suite",
    }
    
    resp = requests.post(
        f"{BASE_URL}/api/skills/select",
        json={"context": context2, "max_skills": 5},
    )
    assert resp.status_code == 200, f"Failed to select skills: {resp.text}"
    
    data = resp.json()
    selected = data.get("selected", [])
    print(f"✅ Context 2 (testing): {len(selected)} skills selected")
    for s in selected:
        print(f"   - {s['name']} (score={s.get('score', 0):.1f})")
    
    # Should select testing-related skills
    test_skills = [s for s in selected if s.get("category") == "testing"]
    print(f"✅ Testing skills: {len(test_skills)}")
    assert len(test_skills) >= 1, "Should select at least one testing skill"
    
    # Test context 3: Debugging
    context3 = {
        "task": "Debug a production issue",
        "task_type": "debugging",
        "description": "Application is crashing with a FileNotFoundError",
    }
    
    resp = requests.post(
        f"{BASE_URL}/api/skills/select",
        json={"context": context3, "max_skills": 5},
    )
    assert resp.status_code == 200, f"Failed to select skills: {resp.text}"
    
    data = resp.json()
    selected = data.get("selected", [])
    print(f"✅ Context 3 (debugging): {len(selected)} skills selected")
    for s in selected:
        print(f"   - {s['name']} (score={s.get('score', 0):.1f})")
    
    # Should select debugging and error handling skills
    debug_skills = [s for s in selected if s.get("category") in ["debugging", "error_handling"]]
    print(f"✅ Debug/error skills: {len(debug_skills)}")
    assert len(debug_skills) >= 1, "Should select at least one debug/error skill"
    
    print()


def test_skill_execution():
    """Test 4: Test skill execution."""
    print("=" * 60)
    print("TEST 4: Skill Execution")
    print("=" * 60)
    
    # Get a skill to execute
    resp = requests.get(f"{BASE_URL}/api/skills")
    data = resp.json()
    skills = data.get("skills", [])
    
    # Find a skill with simple steps (try safe_file_operations first, fall back to any)
    test_skill = None
    for s in skills:
        if s.get("name") == "safe_file_operations":
            test_skill = s
            break
    if not test_skill:
        # Fall back to any skill with steps
        for s in skills:
            if s.get("steps") and len(s["steps"]) > 0:
                test_skill = s
                break
    
    assert test_skill, "Could not find a skill with steps"
    print(f"✅ Selected skill: {test_skill['name']}")
    print(f"   Steps: {len(test_skill.get('steps', []))}")
    
    # Execute the skill
    resp = requests.post(
        f"{BASE_URL}/api/skills/{test_skill['id']}/execute",
        json={
            "context": {
                "task": "Read a file safely",
                "file_path": "/etc/hostname",
            }
        },
    )
    
    assert resp.status_code == 200, f"Failed to execute skill: {resp.text}"
    data = resp.json()
    print(f"✅ Skill executed successfully")
    print(f"   Result: {data.get('result', 'N/A')[:100]}")
    print(f"   Success: {data.get('success', False)}")
    assert data.get("success", False) == True
    
    print()


def test_skill_improvement():
    """Test 5: Test skill improvement."""
    print("=" * 60)
    print("TEST 5: Skill Improvement")
    print("=" * 60)
    
    # Get a skill to improve
    resp = requests.get(f"{BASE_URL}/api/skills")
    data = resp.json()
    skills = data.get("skills", [])
    
    test_skill = None
    for s in skills:
        if s.get("name") == "graceful_error_handling":
            test_skill = s
            break
    
    assert test_skill, "Could not find graceful_error_handling skill"
    old_version = test_skill.get("version", "0.1.0")
    print(f"✅ Selected skill: {test_skill['name']} v{old_version}")
    
    # Improve the skill
    resp = requests.post(
        f"{BASE_URL}/api/skills/{test_skill['id']}/improve",
        json={
            "description": "Improved: Always handle errors gracefully with specific exception types",
            "improvement_note": "Added specific exception handling guidance",
        },
    )
    
    assert resp.status_code == 200, f"Failed to improve skill: {resp.text}"
    
    data = resp.json()
    new_version = data.get("version", "N/A")
    print(f"✅ Skill improved")
    print(f"   Old version: {old_version}")
    print(f"   New version: {new_version}")
    print(f"   Improved: {data.get('improved', False)}")
    
    # Verify version was bumped
    assert new_version != old_version, f"Version should have changed from {old_version} to something else"
    
    print()


def test_deduplication():
    """Test 6: Test deduplication."""
    print("=" * 60)
    print("TEST 6: Deduplication")
    print("=" * 60)
    
    # Create a duplicate skill
    resp = requests.post(
        f"{BASE_URL}/api/skills",
        json={
            "name": "safe_file_operations_v2",
            "description": "Always use safe file operations: check existence before read, validate paths, handle permissions",
            "trigger_conditions": ["file operations", "read file", "write file"],
            "steps": [
                {"action": "check_file_exists", "description": "Verify file exists before reading"},
                {"action": "validate_path", "description": "Sanitize file paths"},
            ],
            "category": "file_operations",
            "source": "test",
        },
    )
    
    assert resp.status_code == 200, f"Failed to create duplicate: {resp.text}"
    print(f"✅ Created duplicate skill: safe_file_operations_v2")
    
    # Find duplicate groups
    resp = requests.get(f"{BASE_URL}/api/skills/dedup/groups?threshold=0.3")
    assert resp.status_code == 200, f"Failed to find duplicates: {resp.text}"
    
    data = resp.json()
    groups = data.get("groups", [])
    print(f"✅ Found {len(groups)} duplicate groups")
    
    for group in groups:
        print(f"   Primary: {group['primary']['name']}")
        for dup in group.get("duplicates", []):
            print(f"     → Duplicate: {dup['name']} (similarity={group.get('similarity', 0):.2f})")
    
    # Merge duplicates
    resp = requests.post(f"{BASE_URL}/api/skills/dedup?threshold=0.3")
    assert resp.status_code == 200, f"Failed to deduplicate: {resp.text}"
    
    data = resp.json()
    print(f"✅ Deduplication stats: {data}")
    print(f"   Merged: {data.get('merged', 0)}")
    print(f"   Deleted: {data.get('deleted', 0)}")
    print(f"   Kept: {data.get('kept', 0)}")
    
    print()


def test_maintenance():
    """Test 7: Test maintenance endpoint."""
    print("=" * 60)
    print("TEST 7: Maintenance")
    print("=" * 60)
    
    resp = requests.post(f"{BASE_URL}/api/skills/maintenance")
    assert resp.status_code == 200, f"Failed to run maintenance: {resp.text}"
    
    data = resp.json()
    print(f"✅ Maintenance completed")
    print(f"   Dedup: {data.get('dedup', {})}")
    print(f"   Prune: {data.get('prune', {})}")
    print(f"   Improvements: {data.get('improvements', 0)}")
    
    print()


def test_error_handling():
    """Test 8: Test error handling."""
    print("=" * 60)
    print("TEST 8: Error Handling")
    print("=" * 60)
    
    # Test non-existent skill
    resp = requests.get(f"{BASE_URL}/api/skills/non-existent-id")
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    print(f"✅ Non-existent skill returns 404")
    
    # Test invalid improvement
    resp = requests.post(
        f"{BASE_URL}/api/skills/non-existent-id/improve",
        json={"description": "test"},
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    print(f"✅ Non-existent skill improvement returns 404")
    
    print()


def test_skill_search():
    """Test 9: Test skill search."""
    print("=" * 60)
    print("TEST 9: Skill Search")
    print("=" * 60)
    
    # Search for file-related skills
    resp = requests.get(f"{BASE_URL}/api/skills/search?query=file")
    assert resp.status_code == 200, f"Failed to search: {resp.text}"
    
    data = resp.json()
    results = data.get("skills", [])
    print(f"✅ Search 'file': {len(results)} results")
    for s in results:
        print(f"   - {s['name']}")
    
    # Search for testing-related skills
    resp = requests.get(f"{BASE_URL}/api/skills/search?query=test")
    assert resp.status_code == 200, f"Failed to search: {resp.text}"
    
    data = resp.json()
    results = data.get("skills", [])
    print(f"✅ Search 'test': {len(results)} results")
    for s in results:
        print(f"   - {s['name']}")
    
    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("TEKTOS SKILL SYSTEM TEST SUITE")
    print("=" * 60 + "\n")
    
    tests = [
        test_skill_listing,
        test_skill_stats,
        test_skill_selection,
        test_skill_execution,
        test_skill_improvement,
        test_deduplication,
        test_maintenance,
        test_error_handling,
        test_skill_search,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}\n")
            failed += 1
    
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
