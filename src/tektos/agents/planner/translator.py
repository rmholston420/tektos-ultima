"""Translator — converts natural language to Proper Technical English.

Natural language is inherently ambiguous — "make it better" means nothing
to an LLM in the context of code generation. The Translator produces:
- Terse output: every word earns its place, context budget is precious
- Unambiguous language: no "maybe," "perhaps," "feel free to" — precise specifications
- Structured format: standardized language the Coding Agent can execute deterministically

This is where the Planner adds the most value — bridging human imprecision
to machine precision. The LLM is the translator layer; Python is the
computation engine. The Translator never does computation.
"""

from __future__ import annotations

import re
from typing import Any


# Fillers and hedging language to strip
_FILLERS = {
    "i think": "",
    "i believe": "",
    "i feel": "",
    "i would": "",
    "i would like to": "",
    "i want": "",
    "i need": "",
    "i would like": "",
    "i was thinking": "",
    "maybe we could": "",
    "perhaps we should": "",
    "feel free to": "",
    "you can": "",
    "you should": "",
    "it would be good to": "",
    "it might be nice to": "",
    "it would be better if": "",
    "i was wondering if": "",
    "could you please": "",
    "would you mind": "",
    "just": " ",
    "simply": " ",
    "basically": "",
    "essentially": "",
    "actually": "",
    "really": "",
    "very": "",
    "quite": "",
    "rather": "",
    "somewhat": "",
    "a bit": "",
    "a little": "",
    "a": " ",
    "an": " ",
}

# Common vague terms with their precise replacements
_VAGUE_TO_PRECISE: dict[str, str] = {
    "fast": "low-latency",
    "slow": "high-latency",
    "good": "meets acceptance criteria",
    "bad": "fails acceptance criteria",
    "big": "large-scale",
    "small": "minimal",
    "simple": "straightforward",
    "complex": "requires careful design",
    "secure": "meets security standards",
    "reliable": "meets uptime/accuracy standards",
    "scalable": "handles increased load",
    "efficient": "optimal resource usage",
    "clean": "well-structured code",
    "modern": "current best practices",
    "user-friendly": "intuitive interface with minimal cognitive load",
    "real-time": "sub-second response time",
}

# Common NL phrases → precise technical descriptions
_PHRASE_REPLACEMENTS: dict[str, str] = {
    "build me an api": "implement RESTful API with",
    "create a database": "design database schema with",
    "write a function": "implement function that",
    "make a website": "develop web application with",
    "add authentication": "implement authentication with",
    "handle errors": "implement error handling with",
    "save to disk": "persist data to",
    "load from file": "read data from",
    "send an email": "send email notification via",
    "call an endpoint": "make HTTP request to",
    "parse json": "deserialize JSON response from",
    "format output": "serialize output as",
    "run tests": "execute test suite with",
    "deploy to production": "deploy to production environment",
    "clone the repo": "clone repository from",
    "install the package": "install package from",
    "update the config": "update configuration with",
    "restart the server": "restart server process",
    "kill the process": "terminate process by",
    "check the logs": "review logs from",
    "look at the code": "analyze code in",
    "fix the bug": "resolve the issue in",
    "refactor this": "restructure for clarity and performance in",
    "optimize this": "optimize for performance in",
    "test this": "write test coverage for",
    "document this": "generate documentation for",
    "add logging": "add structured logging for",
    "add monitoring": "add metrics collection for",
    "add caching": "add caching layer for",
    "add rate limiting": "add rate limiting to",
    "add validation": "add input validation for",
    "add type hints": "add type annotations to",
    "add documentation": "add docstrings and type hints to",
    "remove dead code": "remove unused code from",
    "merge the changes": "merge pull request with",
    "create a branch": "create branch named",
    "commit the changes": "commit changes with message",
    "push to remote": "push to remote repository",
    "pull from remote": "pull from remote repository",
    "reset the branch": "reset branch to",
    "revert the commit": "revert commit with hash",
    "squash the commits": "squash commits into single commit",
    "rebase onto": "rebase onto",
    "check the diff": "review diff between",
    "compare versions": "compare versions and",
    "check the status": "check status of",
    "check the health": "verify health of",
    "check the performance": "measure performance of",
    "check the security": "audit security of",
    "check the tests": "verify test coverage of",
    "check the docs": "review documentation of",
    "check the config": "validate configuration for",
    "check the logs": "review logs for",
    "check the metrics": "collect metrics from",
    "check the alerts": "check alerts for",
    "check the deployments": "check deployments for",
    "check the backups": "verify backups of",
    "check the snapshots": "verify snapshots of",
    "check the state": "verify state of",
    "check the data": "verify data integrity of",
    "check the schema": "verify schema of",
    "check the migrations": "verify migrations for",
    "check the models": "verify models for",
    "check the routes": "verify routes for",
    "check the handlers": "verify handlers for",
    "check the middlewares": "verify middlewares for",
    "check the plugins": "verify plugins for",
    "check the extensions": "verify extensions for",
    "check the adapters": "verify adapters for",
    "check the providers": "verify providers for",
    "check the services": "verify services for",
    "check the controllers": "verify controllers for",
    "check the views": "verify views for",
    "check the templates": "verify templates for",
    "check the styles": "verify styles for",
    "check the scripts": "verify scripts for",
    "check the assets": "verify assets for",
    "check the images": "verify images for",
    "check the fonts": "verify fonts for",
    "check the icons": "verify icons for",
    "check the translations": "verify translations for",
    "check the locales": "verify locales for",
    "check the i18n": "verify internationalization for",
    "check the a11y": "verify accessibility for",
    "check the seo": "verify SEO for",
    "check the analytics": "verify analytics for",
    "check the tracking": "verify tracking for",
    "check the privacy": "verify privacy for",
    "check the gdpr": "verify GDPR compliance for",
    "check the pci": "verify PCI compliance for",
    "check the hipaa": "verify HIPAA compliance for",
    "check the soc": "verify SOC compliance for",
    "check the iso": "verify ISO compliance for",
    "check the nist": "verify NIST compliance for",
    "check the cisa": "verify CISA compliance for",
    "check the mitre": "verify MITRE compliance for",
    "check the owasp": "verify OWASP compliance for",
}


def translate_to_technical_english(text: str) -> str:
    """Convert natural language to Proper Technical English.

    Removes fillers, hedging language, and vague terms. Produces terse,
    unambiguous, context-budget efficient output.

    Args:
        text: The natural language input to translate.

    Returns:
        Proper Technical English translation.
    """
    result = text.lower().strip()

    # Strip fillers and hedging language
    for filler, replacement in _FILLERS.items():
        result = re.sub(rf'\b{re.escape(filler)}\b', replacement, result, flags=re.IGNORECASE)

    # Replace vague terms with precise ones
    for vague, precise in _VAGUE_TO_PRECISE.items():
        result = re.sub(rf'\b{re.escape(vague)}\b', precise, result, flags=re.IGNORECASE)

    # Replace common phrases
    for phrase, replacement in _PHRASE_REPLACEMENTS.items():
        result = re.sub(rf'\b{re.escape(phrase)}\b', replacement, result, flags=re.IGNORECASE)

    # Clean up multiple spaces
    result = re.sub(r'\s+', ' ', result).strip()

    # Remove trailing punctuation for spec format (will be added by spec generator)
    result = result.rstrip('.!,;')

    return result


def add_spec_context(text: str, context: dict[str, Any] | None = None) -> str:
    """Add context to a translated prompt for completeness.

    Args:
        text: The Proper Technical English text.
        context: Optional context dict (language_game, tech_stack, constraints).

    Returns:
        Text with context added as prefix if context is provided.
    """
    if not context:
        return text

    parts = [text]
    if context.get("language_game"):
        parts.append(f"language_game: {context['language_game']}")
    if context.get("tech_stack"):
        parts.append(f"tech_stack: {', '.join(context['tech_stack'])}")
    if context.get("constraints"):
        parts.append(f"constraints: {', '.join(context['constraints'])}")

    return "\n".join(parts)
