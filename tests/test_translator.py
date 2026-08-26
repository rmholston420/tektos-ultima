"""Tests for Translator — converts natural language to Proper Technical English."""

import pytest

from tektos.agents.planner.translator import (
    translate_to_technical_english,
    add_spec_context,
)


class TestTranslateToTechnicalEnglish:
    def test_strips_i_think(self):
        result = translate_to_technical_english("I think we should build an API")
        assert "i think" not in result

    def test_strips_i_want(self):
        result = translate_to_technical_english("I want to create a database")
        assert "i want" not in result

    def test_strips_maybe(self):
        result = translate_to_technical_english("Maybe we could build a website")
        assert "maybe" not in result

    def test_replaces_fast(self):
        result = translate_to_technical_english("Build a fast API")
        assert "low-latency" in result

    def test_replaces_slow(self):
        result = translate_to_technical_english("The system is slow")
        assert "high-latency" in result

    def test_replaces_good(self):
        result = translate_to_technical_english("Build a good API")
        assert "meets acceptance criteria" in result

    def test_replaces_build_me_an_api(self):
        result = translate_to_technical_english("Build me an API with authentication")
        assert "build me api with authentication" in result

    def test_replaces_create_a_database(self):
        result = translate_to_technical_english("Create a database for users")
        assert "create database for users" in result

    def test_removes_trailing_punctuation(self):
        result = translate_to_technical_english("Build an API.")
        assert result.endswith("api")

    def test_cleanups_multiple_spaces(self):
        result = translate_to_technical_english("Build    an    API")
        assert "  " not in result

    def test_case_insensitive(self):
        result = translate_to_technical_english("I WANT to build an API")
        assert "i want" not in result.lower()

    def test_empty_input(self):
        result = translate_to_technical_english("")
        assert result == ""

    def test_preserves_core_content(self):
        result = translate_to_technical_english("Build an API with PostgreSQL and Docker")
        assert "api" in result.lower()
        assert "postgresql" in result.lower()
        assert "docker" in result.lower()

    def test_strips_just(self):
        result = translate_to_technical_english("Just build an API")
        assert "just" not in result.lower()

    def test_strips_simply(self):
        result = translate_to_technical_english("Simply build an API")
        assert "simply" not in result.lower()

    def test_strips_essentially(self):
        result = translate_to_technical_english("Essentially build an API")
        assert "essentially" not in result.lower()

    def test_strips_actually(self):
        result = translate_to_technical_english("Actually build an API")
        assert "actually" not in result.lower()

    def test_strips_very(self):
        result = translate_to_technical_english("Build a very fast API")
        assert "very" not in result.lower()

    def test_strips_feel_free_to(self):
        result = translate_to_technical_english("Feel free to build an API")
        assert "feel free to" not in result.lower()

    def test_strips_you_can(self):
        result = translate_to_technical_english("You can build an API")
        assert "you can" not in result.lower()

    def test_replaces_secure(self):
        result = translate_to_technical_english("Build a secure API")
        assert "meets security standards" in result.lower()

    def test_replaces_scalable(self):
        result = translate_to_technical_english("Build a scalable API")
        assert "handles increased load" in result.lower()

    def test_replaces_add_authentication(self):
        result = translate_to_technical_english("Add authentication to the API")
        assert "implement authentication with" in result.lower()

    def test_replaces_handle_errors(self):
        result = translate_to_technical_english("Handle errors in the API")
        assert "implement error handling with" in result.lower()

    def test_replaces_run_tests(self):
        result = translate_to_technical_english("Run tests for the module")
        assert "execute test suite with" in result.lower()

    def test_replaces_add_logging(self):
        result = translate_to_technical_english("Add logging to the API")
        assert "add structured logging for" in result.lower()

    def test_replaces_add_caching(self):
        result = translate_to_technical_english("Add caching to the API")
        assert "add caching layer for" in result.lower()

    def test_replaces_add_rate_limiting(self):
        result = translate_to_technical_english("Add rate limiting to the API")
        assert "add rate limiting to" in result.lower()

    def test_replaces_add_validation(self):
        result = translate_to_technical_english("Add validation to the API")
        assert "add input validation for" in result.lower()

    def test_replaces_add_type_hints(self):
        result = translate_to_technical_english("Add type hints to the module")
        assert "add type annotations to" in result.lower()

    def test_replaces_remove_dead_code(self):
        result = translate_to_technical_english("Remove dead code from the module")
        assert "remove unused code from" in result.lower()

    def test_replaces_create_a_branch(self):
        result = translate_to_technical_english("Create a branch named feature")
        assert "create branch named" in result.lower()

    def test_replaces_commit_the_changes(self):
        result = translate_to_technical_english("Commit the changes with message")
        assert "commit changes with message" in result.lower()

    def test_replaces_push_to_remote(self):
        result = translate_to_technical_english("Push to remote repository")
        assert "push to remote repository" in result.lower()

    def test_replaces_fix_the_bug(self):
        result = translate_to_technical_english("Fix the bug in the module")
        assert "resolve the issue in" in result.lower()

    def test_replaces_refactor_this(self):
        result = translate_to_technical_english("Refactor this module")
        assert "restructure for clarity and performance in" in result.lower()

    def test_replaces_optimize_this(self):
        result = translate_to_technical_english("Optimize this function")
        assert "optimize for performance in" in result.lower()

    def test_replaces_test_this(self):
        result = translate_to_technical_english("Test this module")
        assert "write test coverage for" in result.lower()

    def test_replaces_document_this(self):
        result = translate_to_technical_english("Document this API")
        assert "generate documentation for" in result.lower()

    def test_replaces_add_monitoring(self):
        result = translate_to_technical_english("Add monitoring to the API")
        assert "add metrics collection for" in result.lower()

    def test_replaces_add_documentation(self):
        result = translate_to_technical_english("Add documentation to the module")
        assert "add docstrings and type hints to" in result.lower()

    def test_replaces_merge_the_changes(self):
        result = translate_to_technical_english("Merge the changes")
        assert "merge pull request with" in result.lower()

    def test_replaces_reset_the_branch(self):
        result = translate_to_technical_english("Reset the branch to main")
        assert "reset branch to" in result.lower()

    def test_replaces_revert_the_commit(self):
        result = translate_to_technical_english("Revert the commit with hash")
        assert "revert commit with hash" in result.lower()

    def test_replaces_squash_the_commits(self):
        result = translate_to_technical_english("Squash the commits into one")
        assert "squash commits into single commit" in result.lower()

    def test_replaces_rebase_onto(self):
        result = translate_to_technical_english("Rebase onto main")
        assert "rebase onto" in result.lower()

    def test_replaces_check_the_diff(self):
        result = translate_to_technical_english("Check the diff between branches")
        assert "review diff between" in result.lower()

    def test_replaces_compare_versions(self):
        result = translate_to_technical_english("Compare versions and merge")
        assert "compare versions and" in result.lower()

    def test_replaces_check_the_status(self):
        result = translate_to_technical_english("Check the status of the build")
        assert "check status of" in result.lower()

    def test_replaces_check_the_health(self):
        result = translate_to_technical_english("Check the health of the server")
        assert "verify health of" in result.lower()

    def test_replaces_check_the_performance(self):
        result = translate_to_technical_english("Check the performance of the API")
        assert "measure performance of" in result.lower()

    def test_replaces_check_the_security(self):
        result = translate_to_technical_english("Check the security of the app")
        assert "audit security of" in result.lower()

    def test_replaces_check_the_tests(self):
        result = translate_to_technical_english("Check the tests for coverage")
        assert "verify test coverage of" in result.lower()

    def test_replaces_check_the_docs(self):
        result = translate_to_technical_english("Check the docs for the API")
        assert "review documentation of" in result.lower()

    def test_replaces_check_the_config(self):
        result = translate_to_technical_english("Check the config for errors")
        assert "validate configuration for" in result.lower()

    def test_replaces_check_the_metrics(self):
        result = translate_to_technical_english("Check the metrics from the server")
        assert "collect metrics from" in result.lower()

    def test_replaces_check_the_alerts(self):
        result = translate_to_technical_english("Check the alerts for the system")
        assert "check alerts for" in result.lower()

    def test_replaces_check_the_deployments(self):
        result = translate_to_technical_english("Check the deployments for the app")
        assert "check deployments for" in result.lower()

    def test_replaces_check_the_backups(self):
        result = translate_to_technical_english("Check the backups of the database")
        assert "verify backups of" in result.lower()

    def test_replaces_check_the_snapshots(self):
        result = translate_to_technical_english("Check the snapshots of the volume")
        assert "verify snapshots of" in result.lower()

    def test_replaces_check_the_state(self):
        result = translate_to_technical_english("Check the state of the system")
        assert "verify state of" in result.lower()

    def test_replaces_check_the_data(self):
        result = translate_to_technical_english("Check the data integrity of the DB")
        assert "verify data integrity of" in result.lower()

    def test_replaces_check_the_schema(self):
        result = translate_to_technical_english("Check the schema of the database")
        assert "verify schema of" in result.lower()

    def test_replaces_check_the_migrations(self):
        result = translate_to_technical_english("Check the migrations for the app")
        assert "verify migrations for" in result.lower()

    def test_replaces_check_the_models(self):
        result = translate_to_technical_english("Check the models for the API")
        assert "verify models for" in result.lower()

    def test_replaces_check_the_routes(self):
        result = translate_to_technical_english("Check the routes for the API")
        assert "verify routes for" in result.lower()

    def test_replaces_check_the_handlers(self):
        result = translate_to_technical_english("Check the handlers for the API")
        assert "verify handlers for" in result.lower()

    def test_replaces_check_the_middlewares(self):
        result = translate_to_technical_english("Check the middlewares for the API")
        assert "verify middlewares for" in result.lower()

    def test_replaces_check_the_plugins(self):
        result = translate_to_technical_english("Check the plugins for the app")
        assert "verify plugins for" in result.lower()

    def test_replaces_check_the_extensions(self):
        result = translate_to_technical_english("Check the extensions for the app")
        assert "verify extensions for" in result.lower()

    def test_replaces_check_the_adapters(self):
        result = translate_to_technical_english("Check the adapters for the API")
        assert "verify adapters for" in result.lower()

    def test_replaces_check_the_providers(self):
        result = translate_to_technical_english("Check the providers for the API")
        assert "verify providers for" in result.lower()

    def test_replaces_check_the_services(self):
        result = translate_to_technical_english("Check the services for the app")
        assert "verify services for" in result.lower()

    def test_replaces_check_the_controllers(self):
        result = translate_to_technical_english("Check the controllers for the API")
        assert "verify controllers for" in result.lower()

    def test_replaces_check_the_views(self):
        result = translate_to_technical_english("Check the views for the app")
        assert "verify views for" in result.lower()

    def test_replaces_check_the_templates(self):
        result = translate_to_technical_english("Check the templates for the app")
        assert "verify templates for" in result.lower()

    def test_replaces_check_the_styles(self):
        result = translate_to_technical_english("Check the styles for the app")
        assert "verify styles for" in result.lower()

    def test_replaces_check_the_scripts(self):
        result = translate_to_technical_english("Check the scripts for the app")
        assert "verify scripts for" in result.lower()

    def test_replaces_check_the_assets(self):
        result = translate_to_technical_english("Check the assets for the app")
        assert "verify assets for" in result.lower()

    def test_replaces_check_the_images(self):
        result = translate_to_technical_english("Check the images for the app")
        assert "verify images for" in result.lower()

    def test_replaces_check_the_fonts(self):
        result = translate_to_technical_english("Check the fonts for the app")
        assert "verify fonts for" in result.lower()

    def test_replaces_check_the_icons(self):
        result = translate_to_technical_english("Check the icons for the app")
        assert "verify icons for" in result.lower()

    def test_replaces_check_the_translations(self):
        result = translate_to_technical_english("Check the translations for the app")
        assert "verify translations for" in result.lower()

    def test_replaces_check_the_locales(self):
        result = translate_to_technical_english("Check the locales for the app")
        assert "verify locales for" in result.lower()

    def test_replaces_check_the_i18n(self):
        result = translate_to_technical_english("Check the i18n for the app")
        assert "verify internationalization for" in result.lower()

    def test_replaces_check_the_a11y(self):
        result = translate_to_technical_english("Check the a11y for the app")
        assert "verify accessibility for" in result.lower()

    def test_replaces_check_the_seo(self):
        result = translate_to_technical_english("Check the SEO for the app")
        assert "verify seo for" in result.lower()

    def test_replaces_check_the_analytics(self):
        result = translate_to_technical_english("Check the analytics for the app")
        assert "verify analytics for" in result.lower()

    def test_replaces_check_the_tracking(self):
        result = translate_to_technical_english("Check the tracking for the app")
        assert "verify tracking for" in result.lower()

    def test_replaces_check_the_privacy(self):
        result = translate_to_technical_english("Check the privacy for the app")
        assert "verify privacy for" in result.lower()

    def test_replaces_check_the_gdpr(self):
        result = translate_to_technical_english("Check the GDPR compliance for the app")
        assert "verify gdpr compliance for" in result.lower()

    def test_replaces_check_the_pci(self):
        result = translate_to_technical_english("Check the PCI compliance for the app")
        assert "verify pci compliance for" in result.lower()

    def test_replaces_check_the_hipaa(self):
        result = translate_to_technical_english("Check the HIPAA compliance for the app")
        assert "verify hipaa compliance for" in result.lower()

    def test_replaces_check_the_soc(self):
        result = translate_to_technical_english("Check the SOC compliance for the app")
        assert "verify soc compliance for" in result.lower()

    def test_replaces_check_the_iso(self):
        result = translate_to_technical_english("Check the ISO compliance for the app")
        assert "verify iso compliance for" in result.lower()

    def test_replaces_check_the_nist(self):
        result = translate_to_technical_english("Check the NIST compliance for the app")
        assert "verify nist compliance for" in result.lower()

    def test_replaces_check_the_cisa(self):
        result = translate_to_technical_english("Check the CISA compliance for the app")
        assert "verify cisa compliance for" in result.lower()

    def test_replaces_check_the_mitre(self):
        result = translate_to_technical_english("Check the MITRE compliance for the app")
        assert "verify mitre compliance for" in result.lower()

    def test_replaces_check_the_owasp(self):
        result = translate_to_technical_english("Check the OWASP compliance for the app")
        assert "verify owasp compliance for" in result.lower()

    def test_replaces_real_time(self):
        result = translate_to_technical_english("Build a real-time API")
        assert "sub-second response time" in result.lower()

    def test_replaces_user_friendly(self):
        result = translate_to_technical_english("Build a user-friendly interface")
        assert "intuitive interface with minimal cognitive load" in result.lower()

    def test_replaces_modern(self):
        result = translate_to_technical_english("Build a modern API")
        assert "current best practices" in result.lower()

    def test_replaces_efficient(self):
        result = translate_to_technical_english("Build an efficient API")
        assert "optimal resource usage" in result.lower()

    def test_replaces_clean(self):
        result = translate_to_technical_english("Build a clean API")
        assert "well-structured code" in result.lower()

    def test_replaces_reliable(self):
        result = translate_to_technical_english("Build a reliable API")
        assert "meets uptime/accuracy standards" in result.lower()

    def test_replaces_big(self):
        result = translate_to_technical_english("Build a big API")
        assert "large-scale" in result.lower()

    def test_replaces_small(self):
        result = translate_to_technical_english("Build a small API")
        assert "minimal" in result.lower()

    def test_replaces_simple(self):
        result = translate_to_technical_english("Build a simple API")
        assert "straightforward" in result.lower()

    def test_replaces_complex(self):
        result = translate_to_technical_english("Build a complex API")
        assert "requires careful design" in result.lower()

    def test_replaces_bad(self):
        result = translate_to_technical_english("Build a bad API")
        assert "fails acceptance criteria" in result.lower()

    def test_multiple_replacements(self):
        result = translate_to_technical_english("I think we should build a fast and secure API")
        assert "i think" not in result
        assert "low-latency" in result
        assert "meets security standards" in result

    def test_preserves_newlines(self):
        result = translate_to_technical_english("Build an API\nwith PostgreSQL")
        assert "api" in result.lower()
        assert "postgresql" in result.lower()

    def test_strips_i_would_like_to(self):
        result = translate_to_technical_english("I would like to build an API")
        assert "i would like to" not in result.lower()

    def test_strips_i_was_thinking(self):
        result = translate_to_technical_english("I was thinking we should build an API")
        assert "i was thinking" not in result.lower()

    def test_strips_could_you_please(self):
        result = translate_to_technical_english("Could you please build an API")
        assert "could you please" not in result.lower()

    def test_strips_would_you_mind(self):
        result = translate_to_technical_english("Would you mind building an API")
        assert "would you mind" not in result.lower()

    def test_strips_it_would_be_good_to(self):
        result = translate_to_technical_english("It would be good to build an API")
        assert "it would be good to" not in result.lower()

    def test_strips_it_might_be_nice_to(self):
        result = translate_to_technical_english("It might be nice to build an API")
        assert "it might be nice to" not in result.lower()

    def test_strips_it_would_be_better_if(self):
        result = translate_to_technical_english("It would be better if we build an API")
        assert "it would be better if" not in result.lower()

    def test_strips_i_was_wondering_if(self):
        result = translate_to_technical_english("I was wondering if we could build an API")
        assert "i was wondering if" not in result.lower()

    def test_strips_i_believe(self):
        result = translate_to_technical_english("I believe we should build an API")
        assert "i believe" not in result.lower()

    def test_strips_i_feel(self):
        result = translate_to_technical_english("I feel we should build an API")
        assert "i feel" not in result.lower()

    def test_strips_i_would(self):
        result = translate_to_technical_english("I would build an API")
        assert "i would" not in result.lower()

    def test_strips_i_need(self):
        result = translate_to_technical_english("I need to build an API")
        assert "i need" not in result.lower()

    def test_strips_i_would_like(self):
        result = translate_to_technical_english("I would like to build an API")
        assert "i would like" not in result.lower()

    def test_strips_perhaps_we_should(self):
        result = translate_to_technical_english("Perhaps we should build an API")
        assert "perhaps we should" not in result.lower()

    def test_strips_you_should(self):
        result = translate_to_technical_english("You should build an API")
        assert "you should" not in result.lower()

    def test_strips_quite(self):
        result = translate_to_technical_english("Build a quite fast API")
        assert "quite" not in result.lower()

    def test_strips_rather(self):
        result = translate_to_technical_english("Build a rather fast API")
        assert "rather" not in result.lower()

    def test_strips_somewhat(self):
        result = translate_to_technical_english("Build a somewhat fast API")
        assert "somewhat" not in result.lower()

    def test_strips_a_bit(self):
        result = translate_to_technical_english("Build a a bit fast API")
        assert "a bit" not in result.lower()

    def test_strips_a_little(self):
        result = translate_to_technical_english("Build a a little fast API")
        assert "a little" not in result.lower()


class TestAddSpecContext:
    def test_no_context(self):
        result = add_spec_context("build an api")
        assert result == "build an api"

    def test_with_language_game(self):
        result = add_spec_context("build an api", {"language_game": "software_engineering"})
        assert "language_game: software_engineering" in result

    def test_with_tech_stack(self):
        result = add_spec_context("build an api", {"tech_stack": ["python", "fastapi"]})
        assert "tech_stack: python, fastapi" in result

    def test_with_constraints(self):
        result = add_spec_context("build an api", {"constraints": ["no external deps"]})
        assert "constraints: no external deps" in result

    def test_with_all_context(self):
        result = add_spec_context("build an api", {
            "language_game": "software_engineering",
            "tech_stack": ["python"],
            "constraints": ["no external deps"],
        })
        assert "language_game: software_engineering" in result
        assert "tech_stack: python" in result
        assert "constraints: no external deps" in result

    def test_newline_separation(self):
        result = add_spec_context("build an api", {"language_game": "general"})
        lines = result.split("\n")
        assert len(lines) == 2
