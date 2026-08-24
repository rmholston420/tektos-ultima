#!/usr/bin/env python3
"""Pre-seed Tektos with an optimal set of skills.

This script creates a comprehensive skill set covering:
- File operations best practices
- Error handling patterns
- Testing patterns
- Git workflow
- Code quality
- Debugging patterns
- Architecture patterns
- Security patterns
- Performance patterns
- Self-improvement patterns
"""

import sys
import os
import uuid
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tektos.skills.registry import SkillRegistry, Skill
from tektos.skills.manager import SkillManager

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "tektos.db"
SKILL_DIR = Path.home() / ".tektos/skills"


def create_preseed_skills():
    """Create the optimal pre-seed skill set."""
    
    reg = SkillRegistry(db_path=str(DB_PATH), skill_dir=str(SKILL_DIR))
    mgr = SkillManager(registry=reg)
    
    # Define all pre-seed skills
    skills = [
        # ── File Operations ──────────────────────────────────────────────
        {
            "name": "safe_file_operations",
            "description": "Always use safe file operations: check existence before read, validate paths, handle permissions",
            "trigger_conditions": [
                "file operations",
                "read file",
                "write file",
                "path validation",
                "permission check",
            ],
            "steps": [
                {
                    "action": "check_file_exists",
                    "description": "Verify file exists before reading",
                },
                {
                    "action": "validate_path",
                    "description": "Sanitize file paths to prevent directory traversal",
                },
                {
                    "action": "check_permissions",
                    "description": "Verify read/write permissions before operations",
                },
                {
                    "action": "use_context_manager",
                    "description": "Use context managers (with statement) for file operations",
                },
            ],
            "category": "file_operations",
            "source": "preseed",
        },
        {
            "name": "pathlib_best_practices",
            "description": "Use pathlib.Path for all file path operations instead of string concatenation",
            "trigger_conditions": [
                "file path",
                "path manipulation",
                "file operations",
                "os.path",
            ],
            "steps": [
                {
                    "action": "use_pathlib",
                    "description": "Replace os.path with pathlib.Path for path operations",
                },
                {
                    "action": "path_join",
                    "description": "Use Path.joinpath() instead of string concatenation",
                },
                {
                    "action": "path_resolve",
                    "description": "Use Path.resolve() to get absolute paths",
                },
            ],
            "category": "file_operations",
            "source": "preseed",
        },
        
        # ── Error Handling ───────────────────────────────────────────────
        {
            "name": "graceful_error_handling",
            "description": "Implement comprehensive error handling with specific exception types and meaningful error messages",
            "trigger_conditions": [
                "error handling",
                "exception",
                "try except",
                "error handling",
                "fail gracefully",
            ],
            "steps": [
                {
                    "action": "specific_exceptions",
                    "description": "Catch specific exceptions, not bare except",
                },
                {
                    "action": "error_logging",
                    "description": "Log errors with context (file, line, parameters)",
                },
                {
                    "action": "user_friendly_messages",
                    "description": "Provide user-friendly error messages",
                },
                {
                    "action": "cleanup_on_error",
                    "description": "Ensure cleanup happens even on error (use finally or context managers)",
                },
            ],
            "category": "error_handling",
            "source": "preseed",
        },
        {
            "name": "file_not_found_handling",
            "description": "Always handle FileNotFoundError gracefully with clear error messages and fallbacks",
            "trigger_conditions": [
                "file not found",
                "FileNotFoundError",
                "missing file",
                "file read",
            ],
            "steps": [
                {
                    "action": "check_existence",
                    "description": "Check file existence before operations",
                },
                {
                    "action": "graceful_fallback",
                    "description": "Provide fallback behavior when file is missing",
                },
                {
                    "action": "clear_error_message",
                    "description": "Provide clear error message with file path and suggested actions",
                },
            ],
            "category": "error_handling",
            "source": "preseed",
        },
        
        # ── Testing ──────────────────────────────────────────────────────
        {
            "name": "test_driven_development",
            "description": "Write tests before implementation (RED-GREEN-REFACTOR cycle)",
            "trigger_conditions": [
                "testing",
                "test driven",
                "unit test",
                "pytest",
                "test first",
            ],
            "steps": [
                {
                    "action": "write_test_first",
                    "description": "Write failing test before implementation",
                },
                {
                    "action": "implement_minimal",
                    "description": "Implement minimal code to pass test",
                },
                {
                    "action": "refactor",
                    "description": "Refactor code while keeping tests green",
                },
                {
                    "action": "run_test_suite",
                    "description": "Run full test suite to ensure no regressions",
                },
            ],
            "category": "testing",
            "source": "preseed",
        },
        {
            "name": "comprehensive_testing",
            "description": "Write comprehensive tests covering happy path, edge cases, and error conditions",
            "trigger_conditions": [
                "test coverage",
                "edge cases",
                "error conditions",
                "test suite",
                "pytest",
            ],
            "steps": [
                {
                    "action": "happy_path",
                    "description": "Test normal/expected behavior",
                },
                {
                    "action": "edge_cases",
                    "description": "Test boundary conditions and edge cases",
                },
                {
                    "action": "error_paths",
                    "description": "Test error handling and failure modes",
                },
                {
                    "action": "mock_external",
                    "description": "Mock external dependencies (APIs, databases, filesystem)",
                },
            ],
            "category": "testing",
            "source": "preseed",
        },
        
        # ── Git Workflow ─────────────────────────────────────────────────
        {
            "name": "git_best_practices",
            "description": "Follow git best practices: atomic commits, meaningful messages, feature branches",
            "trigger_conditions": [
                "git",
                "commit",
                "branch",
                "version control",
                "merge",
            ],
            "steps": [
                {
                    "action": "atomic_commits",
                    "description": "Make small, atomic commits with clear purpose",
                },
                {
                    "action": "meaningful_messages",
                    "description": "Write clear, descriptive commit messages",
                },
                {
                    "action": "feature_branches",
                    "description": "Use feature branches for development",
                },
                {
                    "action": "merge_strategy",
                    "description": "Merge completed work to main, don't leave on branches",
                },
            ],
            "category": "git",
            "source": "preseed",
        },
        
        # ── Code Quality ─────────────────────────────────────────────────
        {
            "name": "code_quality_standards",
            "description": "Maintain high code quality: type hints, docstrings, consistent style, no magic numbers",
            "trigger_conditions": [
                "code quality",
                "type hints",
                "docstrings",
                "style",
                "clean code",
            ],
            "steps": [
                {
                    "action": "add_type_hints",
                    "description": "Add type hints to function signatures",
                },
                {
                    "action": "write_docstrings",
                    "description": "Write clear docstrings for functions and classes",
                },
                {
                    "action": "consistent_style",
                    "description": "Follow consistent coding style (PEP 8, project conventions)",
                },
                {
                    "action": "remove_magic",
                    "description": "Replace magic numbers/strings with named constants",
                },
            ],
            "category": "code_quality",
            "source": "preseed",
        },
        {
            "name": "dry_principle",
            "description": "Don't Repeat Yourself: extract common patterns into reusable functions",
            "trigger_conditions": [
                "DRY",
                "code duplication",
                "refactor",
                "reusable",
                "extract",
            ],
            "steps": [
                {
                    "action": "identify_duplication",
                    "description": "Identify repeated code patterns",
                },
                {
                    "action": "extract_function",
                    "description": "Extract common logic into reusable functions",
                },
                {
                    "action": "parameterize",
                    "description": "Parameterize extracted functions for flexibility",
                },
            ],
            "category": "code_quality",
            "source": "preseed",
        },
        
        # ── Debugging ────────────────────────────────────────────────────
        {
            "name": "systematic_debugging",
            "description": "Use systematic debugging: reproduce, isolate, hypothesize, test, verify",
            "trigger_conditions": [
                "debug",
                "bug",
                "error",
                "investigate",
                "root cause",
            ],
            "steps": [
                {
                    "action": "reproduce",
                    "description": "Reproduce the bug consistently",
                },
                {
                    "action": "isolate",
                    "description": "Isolate the problem to smallest reproducible case",
                },
                {
                    "action": "hypothesize",
                    "description": "Form hypothesis about root cause",
                },
                {
                    "action": "test_hypothesis",
                    "description": "Test hypothesis with targeted experiments",
                },
                {
                    "action": "verify_fix",
                    "description": "Verify fix and check for regressions",
                },
            ],
            "category": "debugging",
            "source": "preseed",
        },
        
        # ── Architecture ─────────────────────────────────────────────────
        {
            "name": "separation_of_concerns",
            "description": "Separate concerns: keep business logic, I/O, and UI code in separate modules",
            "trigger_conditions": [
                "architecture",
                "separation of concerns",
                "modular",
                "clean architecture",
                "layered",
            ],
            "steps": [
                {
                    "action": "identify_concerns",
                    "description": "Identify distinct concerns in the codebase",
                },
                {
                    "action": "create_modules",
                    "description": "Create separate modules for each concern",
                },
                {
                    "action": "define_interfaces",
                    "description": "Define clear interfaces between modules",
                },
            ],
            "category": "architecture",
            "source": "preseed",
        },
        {
            "name": "event_driven_design",
            "description": "Use event-driven architecture for decoupled, scalable systems",
            "trigger_conditions": [
                "event driven",
                "event bus",
                "pub/sub",
                "decoupled",
                "scalable",
            ],
            "steps": [
                {
                    "action": "define_events",
                    "description": "Define clear event types and payloads",
                },
                {
                    "action": "implement_bus",
                    "description": "Implement event bus for message routing",
                },
                {
                    "action": "subscribe_handlers",
                    "description": "Subscribe handlers to relevant events",
                },
            ],
            "category": "architecture",
            "source": "preseed",
        },
        
        # ── Security ─────────────────────────────────────────────────────
        {
            "name": "security_best_practices",
            "description": "Follow security best practices: input validation, secret management, least privilege",
            "trigger_conditions": [
                "security",
                "input validation",
                "secrets",
                "authentication",
                "authorization",
            ],
            "steps": [
                {
                    "action": "validate_input",
                    "description": "Validate and sanitize all user input",
                },
                {
                    "action": "manage_secrets",
                    "description": "Use environment variables or secret managers for credentials",
                },
                {
                    "action": "least_privilege",
                    "description": "Follow principle of least privilege for access control",
                },
                {
                    "action": "audit_logging",
                    "description": "Implement audit logging for security-sensitive operations",
                },
            ],
            "category": "security",
            "source": "preseed",
        },
        
        # ── Performance ──────────────────────────────────────────────────
        {
            "name": "performance_optimization",
            "description": "Optimize performance: profile before optimizing, use efficient algorithms, cache results",
            "trigger_conditions": [
                "performance",
                "optimization",
                "slow",
                "profiling",
                "cache",
            ],
            "steps": [
                {
                    "action": "profile_first",
                    "description": "Profile code to identify actual bottlenecks",
                },
                {
                    "action": "efficient_algorithms",
                    "description": "Use efficient algorithms and data structures",
                },
                {
                    "action": "cache_results",
                    "description": "Cache expensive computations when appropriate",
                },
                {
                    "action": "async_io",
                    "description": "Use async I/O for I/O-bound operations",
                },
            ],
            "category": "performance",
            "source": "preseed",
        },
        
        # ── Self-Improvement ─────────────────────────────────────────────
        {
            "name": "reflection_based_improvement",
            "description": "Use reflection after each session to identify lessons, patterns, and improvements",
            "trigger_conditions": [
                "reflection",
                "self-improvement",
                "lessons learned",
                "what worked",
                "what failed",
            ],
            "steps": [
                {
                    "action": "analyze_session",
                    "description": "Analyze session for patterns and lessons",
                },
                {
                    "action": "extract_lessons",
                    "description": "Extract generalizable lessons from experience",
                },
                {
                    "action": "create_skills",
                    "description": "Convert valuable patterns into reusable skills",
                },
                {
                    "action": "update_practices",
                    "description": "Update practices based on what worked and what failed",
                },
            ],
            "category": "self_improvement",
            "source": "preseed",
        },
        {
            "name": "skill_lifecycle_management",
            "description": "Manage skill lifecycle: create, select, execute, evaluate, deduplicate, improve, prune",
            "trigger_conditions": [
                "skill management",
                "skill lifecycle",
                "deduplication",
                "skill improvement",
                "skill pruning",
            ],
            "steps": [
                {
                    "action": "create_skills",
                    "description": "Create skills from reflection and user input",
                },
                {
                    "action": "select_skills",
                    "description": "Select relevant skills based on context",
                },
                {
                    "action": "execute_skills",
                    "description": "Execute selected skills with proper error handling",
                },
                {
                    "action": "evaluate_skills",
                    "description": "Evaluate skill effectiveness and usage",
                },
                {
                    "action": "deduplicate_skills",
                    "description": "Find and merge duplicate skills",
                },
                {
                    "action": "improve_skills",
                    "description": "Improve skills based on execution results",
                },
                {
                    "action": "prune_skills",
                    "description": "Archive or delete low-performing skills",
                },
            ],
            "category": "self_improvement",
            "source": "preseed",
        },
        
        # ── API Development ──────────────────────────────────────────────
        {
            "name": "fastapi_best_practices",
            "description": "Follow FastAPI best practices: type hints, dependency injection, error handling, documentation",
            "trigger_conditions": [
                "FastAPI",
                "REST API",
                "endpoint",
                "dependency injection",
                "API development",
            ],
            "steps": [
                {
                    "action": "type_hints",
                    "description": "Use type hints for request/response models",
                },
                {
                    "action": "dependency_injection",
                    "description": "Use FastAPI's dependency injection for shared resources",
                },
                {
                    "action": "error_handling",
                    "description": "Implement consistent error handling with HTTPException",
                },
                {
                    "action": "documentation",
                    "description": "Add docstrings and descriptions for API documentation",
                },
            ],
            "category": "api_development",
            "source": "preseed",
        },
        
        # ── Database ─────────────────────────────────────────────────────
        {
            "name": "sqlite_best_practices",
            "description": "Follow SQLite best practices: WAL mode, transactions, proper indexing, connection management",
            "trigger_conditions": [
                "SQLite",
                "database",
                "transaction",
                "indexing",
                "connection",
            ],
            "steps": [
                {
                    "action": "wal_mode",
                    "description": "Enable WAL mode for better concurrency",
                },
                {
                    "action": "use_transactions",
                    "description": "Use transactions for data integrity",
                },
                {
                    "action": "proper_indexing",
                    "description": "Add indexes for frequently queried columns",
                },
                {
                    "action": "connection_management",
                    "description": "Manage database connections properly (close when done)",
                },
            ],
            "category": "database",
            "source": "preseed",
        },
        
        # ── Async Programming ────────────────────────────────────────────
        {
            "name": "async_best_practices",
            "description": "Follow async best practices: use async/await consistently, handle errors, avoid blocking calls",
            "trigger_conditions": [
                "async",
                "await",
                "asyncio",
                "concurrent",
                "non-blocking",
            ],
            "steps": [
                {
                    "action": "async_await",
                    "description": "Use async/await consistently for async operations",
                },
                {
                    "action": "avoid_blocking",
                    "description": "Avoid blocking calls in async code (use run_in_executor)",
                },
                {
                    "action": "error_handling",
                    "description": "Handle async errors properly (try/except around await)",
                },
                {
                    "action": "timeout_handling",
                    "description": "Implement timeouts for async operations",
                },
            ],
            "category": "async_programming",
            "source": "preseed",
        },
        
        # ── Configuration ────────────────────────────────────────────────
        {
            "name": "configuration_management",
            "description": "Manage configuration properly: environment variables, config files, defaults, validation",
            "trigger_conditions": [
                "configuration",
                "environment variables",
                "config",
                "settings",
                "defaults",
            ],
            "steps": [
                {
                    "action": "env_variables",
                    "description": "Use environment variables for sensitive configuration",
                },
                {
                    "action": "config_files",
                    "description": "Use config files for non-sensitive settings",
                },
                {
                    "action": "defaults",
                    "description": "Provide sensible defaults for all configuration",
                },
                {
                    "action": "validate_config",
                    "description": "Validate configuration at startup",
                },
            ],
            "category": "configuration",
            "source": "preseed",
        },
        
        # ── Logging ──────────────────────────────────────────────────────
        {
            "name": "structured_logging",
            "description": "Use structured logging: consistent format, appropriate log levels, contextual information",
            "trigger_conditions": [
                "logging",
                "log",
                "debug",
                "info",
                "warning",
            ],
            "steps": [
                {
                    "action": "consistent_format",
                    "description": "Use consistent log format across the application",
                },
                {
                    "action": "appropriate_levels",
                    "description": "Use appropriate log levels (DEBUG, INFO, WARNING, ERROR)",
                },
                {
                    "action": "contextual_info",
                    "description": "Include contextual information in log messages",
                },
                {
                    "action": "avoid_sensitive",
                    "description": "Never log sensitive information (passwords, tokens, PII)",
                },
            ],
            "category": "logging",
            "source": "preseed",
        },
        
        # ── Documentation ────────────────────────────────────────────────
        {
            "name": "code_documentation",
            "description": "Document code effectively: docstrings, README, architecture docs, inline comments for complex logic",
            "trigger_conditions": [
                "documentation",
                "docstring",
                "README",
                "architecture",
                "comments",
            ],
            "steps": [
                {
                    "action": "docstrings",
                    "description": "Write comprehensive docstrings for public APIs",
                },
                {
                    "action": "readme",
                    "description": "Maintain up-to-date README with setup and usage instructions",
                },
                {
                    "action": "architecture_docs",
                    "description": "Document architecture decisions and system design",
                },
                {
                    "action": "inline_comments",
                    "description": "Add inline comments for complex or non-obvious logic",
                },
            ],
            "category": "documentation",
            "source": "preseed",
        },
        
        # ── Deployment ───────────────────────────────────────────────────
        {
            "name": "deployment_best_practices",
            "description": "Follow deployment best practices: containerization, environment parity, health checks, rollback",
            "trigger_conditions": [
                "deployment",
                "docker",
                "container",
                "production",
                "rollback",
            ],
            "steps": [
                {
                    "action": "containerize",
                    "description": "Containerize application with Docker for consistency",
                },
                {
                    "action": "env_parity",
                    "description": "Maintain parity between development, staging, and production environments",
                },
                {
                    "action": "health_checks",
                    "description": "Implement health check endpoints",
                },
                {
                    "action": "rollback_plan",
                    "description": "Have a rollback plan for deployments",
                },
            ],
            "category": "deployment",
            "source": "preseed",
        },
    ]
    
    # Create skills
    created_count = 0
    skipped_count = 0
    
    for skill_data in skills:
        # Check if skill already exists
        existing = reg.get_by_name(skill_data["name"])
        if existing:
            print(f"  ⏭️  Skipping (exists): {skill_data['name']}")
            skipped_count += 1
            continue
        
        # Create skill
        skill = Skill(
            id=str(uuid.uuid4()),
            name=skill_data["name"],
            description=skill_data["description"],
            trigger_conditions=skill_data["trigger_conditions"],
            steps=skill_data["steps"],
            category=skill_data["category"],
            source=skill_data["source"],
        )
        
        try:
            reg.create(skill)
            print(f"  ✅ Created: {skill_data['name']}")
            created_count += 1
        except Exception as e:
            print(f"  ❌ Failed: {skill_data['name']} - {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Pre-seed complete!")
    print(f"  Created: {created_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Total in DB: {len(reg.list_skills(active_only=False))}")
    print(f"{'='*60}")
    
    reg.close()
    return created_count, skipped_count


if __name__ == "__main__":
    created, skipped = create_preseed_skills()
    sys.exit(0 if created > 0 else 1)
