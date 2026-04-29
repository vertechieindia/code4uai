"""Comprehensive Unit Tests for Day 19-21 modules.

Covers: Pattern Extractor, Wisdom Agent, Legal Agent, Provenance Tracker,
Toxic Scanner, Redis Cache, Partitioned Vector Store, Launch Routes.

Testing types: Unit, White Box, Smoke, Sanity, Regression.
"""

from __future__ import annotations

import json
import os
import time
import pytest
from typing import Dict, Any


# ═══════════════════════════════════════════════════════════════
# Day 19: Collective Intelligence
# ═══════════════════════════════════════════════════════════════

class TestPatternExtractor:
    """Unit tests for PatternExtractor (pattern_extractor.py)."""

    def test_anonymize_removes_emails(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        result = pe.anonymize("send to admin@company.com please")
        assert "admin@company.com" not in result
        assert "EMAIL_REDACTED" in result

    def test_anonymize_removes_aws_keys(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        result = pe.anonymize("key = AKIAIOSFODNN7EXAMPLE")
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "AWS_KEY_REDACTED" in result

    def test_anonymize_removes_ip_addresses(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        result = pe.anonymize("server at 192.168.1.100")
        assert "192.168.1.100" not in result
        assert "IP_REDACTED" in result

    def test_anonymize_removes_uuids(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        result = pe.anonymize("id=550e8400-e29b-41d4-a716-446655440000")
        assert "550e8400" not in result
        assert "UUID_REDACTED" in result

    def test_anonymize_removes_passwords(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        result = pe.anonymize('password = "super_secret_123"')
        assert "super_secret_123" not in result
        assert "REDACTED" in result

    def test_anonymize_removes_api_keys(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        result = pe.anonymize('api_key = "sk-1234567890abcdef"')
        assert "sk-1234567890abcdef" not in result

    def test_anonymize_removes_urls(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        result = pe.anonymize("endpoint = https://internal.corp.com/api/v1")
        assert "internal.corp.com" not in result
        assert "URL_REDACTED" in result

    def test_extract_pattern_creates_nugget(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        nugget = pe.extract_pattern(
            before="eval(user_input)",
            after="safe_eval(sanitize(user_input))",
            language="python",
            pattern_type="security_fix",
            description="Removed dangerous eval",
        )
        assert nugget.nugget_id
        assert nugget.pattern_type == "security_fix"
        assert nugget.language == "python"
        assert "eval" not in nugget.before_snippet or "safe_eval" in nugget.after_snippet

    def test_extract_pattern_hashes_project(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        nugget = pe.extract_pattern(
            before="x=1", after="x=2",
            source_project="my-secret-project",
        )
        assert nugget.source_project != "my-secret-project"
        assert len(nugget.source_project) == 12

    def test_extract_pattern_truncates_long_snippets(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        long_code = "x = 1\n" * 500
        nugget = pe.extract_pattern(before=long_code, after=long_code)
        assert len(nugget.before_snippet) <= 2000
        assert len(nugget.after_snippet) <= 2000

    def test_auto_describe_detects_eval_removal(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        desc = pe._auto_describe("eval(x)", "safe(x)", "python")
        assert "eval" in desc.lower()

    def test_auto_describe_detects_error_handling(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        desc = pe._auto_describe("x = 1", "try:\n    x = 1\nexcept:", "python")
        assert "error" in desc.lower()

    def test_auto_tag_detects_sql(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        tags = pe._auto_tag("SELECT * FROM users", "parameterized query")
        assert "sql" in tags

    def test_auto_tag_detects_credentials(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        tags = pe._auto_tag("password = 'abc'", "password = os.env['PASS']")
        assert "credentials" in tags

    def test_search_nuggets_finds_matches(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        pe.extract_pattern(
            before="SELECT * FROM users WHERE id='" + "' + user_id",
            after="cursor.execute('SELECT * FROM users WHERE id=?', (user_id,))",
            language="python",
            pattern_type="security_fix",
            tags=["sql", "injection"],
        )
        results = pe.search_nuggets("sql injection query")
        assert len(results) > 0

    def test_search_nuggets_filters_by_language(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        pe.extract_pattern(before="x=1", after="x=2", language="python")
        pe.extract_pattern(before="let x=1", after="let x=2", language="javascript")
        results = pe.search_nuggets("x variable", language="python")
        for r in results:
            assert r.language == "python"

    def test_get_stats_counts_correctly(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        pe.extract_pattern(before="a", after="b", pattern_type="bug_fix", language="python")
        pe.extract_pattern(before="c", after="d", pattern_type="security_fix", language="go")
        stats = pe.get_stats()
        assert stats["totalNuggets"] == 2
        assert stats["byType"]["bug_fix"] == 1
        assert stats["byType"]["security_fix"] == 1
        assert stats["byLanguage"]["python"] == 1
        assert stats["byLanguage"]["go"] == 1

    def test_to_dict_uses_camel_case(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        nugget = pe.extract_pattern(before="a", after="b")
        d = nugget.to_dict()
        assert "nuggetId" in d
        assert "patternType" in d
        assert "beforeSnippet" in d
        assert "afterSnippet" in d
        assert "sourceProject" in d
        assert "createdAt" in d

    def test_compute_confidence_same_code_low(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        conf = pe._compute_confidence("same", "same")
        assert conf < 0.2

    def test_compute_confidence_empty_code_low(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        conf = pe._compute_confidence("", "x=1")
        assert conf <= 0.3

    def test_singleton_returns_same_instance(self):
        from code4u.knowledge.pattern_extractor import PatternExtractor, get_pattern_extractor
        import code4u.knowledge.pattern_extractor as mod
        mod._extractor_singleton = None
        a = get_pattern_extractor()
        b = get_pattern_extractor()
        assert a is b


class TestWisdomAgent:
    """Unit tests for WisdomAgent (wisdom_agent.py)."""

    def test_detect_language_python(self):
        from code4u.agents.wisdom_agent import WisdomAgent
        agent = WisdomAgent()
        assert agent._detect_language("src/app.py") == "python"

    def test_detect_language_typescript(self):
        from code4u.agents.wisdom_agent import WisdomAgent
        agent = WisdomAgent()
        assert agent._detect_language("src/app.tsx") == "typescript"

    def test_detect_language_go(self):
        from code4u.agents.wisdom_agent import WisdomAgent
        agent = WisdomAgent()
        assert agent._detect_language("main.go") == "go"

    def test_detect_language_unknown(self):
        from code4u.agents.wisdom_agent import WisdomAgent
        agent = WisdomAgent()
        assert agent._detect_language("Makefile") == "unknown"

    def test_detect_anti_patterns_eval(self):
        from code4u.agents.wisdom_agent import WisdomAgent
        agent = WisdomAgent()
        patterns = agent._detect_known_anti_patterns("app.py", "result = eval(user_input)")
        assert any("eval" in p["description"].lower() for p in patterns)

    def test_detect_anti_patterns_sql_injection(self):
        from code4u.agents.wisdom_agent import WisdomAgent
        agent = WisdomAgent()
        code = 'query = f"SELECT * FROM users WHERE id={uid}"'
        patterns = agent._detect_known_anti_patterns("db.py", code)
        assert any("sql" in p["description"].lower() for p in patterns)

    def test_detect_anti_patterns_hardcoded_password(self):
        from code4u.agents.wisdom_agent import WisdomAgent
        agent = WisdomAgent()
        patterns = agent._detect_known_anti_patterns("config.py", 'password = "admin123"')
        assert any("password" in p["description"].lower() for p in patterns)

    def test_detect_anti_patterns_limits_to_5(self):
        from code4u.agents.wisdom_agent import WisdomAgent
        agent = WisdomAgent()
        code = 'eval(x)\npassword="a"\nprint("debug")\ntime.sleep(1)\n# TODO\ndata.readlines()\ninnerHTML = x'
        patterns = agent._detect_known_anti_patterns("bad.py", code)
        assert len(patterns) <= 5

    def test_extract_functions_python(self):
        from code4u.agents.wisdom_agent import WisdomAgent
        agent = WisdomAgent()
        code = "def hello():\n    return 'hi'\n\ndef goodbye():\n    return 'bye'\n"
        funcs = agent._extract_functions("app.py", code)
        names = [f[0] for f in funcs]
        assert "hello" in names
        assert "goodbye" in names

    def test_extract_functions_javascript(self):
        from code4u.agents.wisdom_agent import WisdomAgent
        agent = WisdomAgent()
        code = "function greet() { return 'hi'; }\nconst farewell = () => 'bye';"
        funcs = agent._extract_functions("app.js", code)
        names = [f[0] for f in funcs]
        assert "greet" in names
        assert "farewell" in names

    def test_analyze_code_returns_suggestions(self):
        from code4u.agents.wisdom_agent import WisdomAgent
        agent = WisdomAgent()
        suggestions = agent.analyze_code_for_suggestions({"test.py": "eval(x)"})
        assert isinstance(suggestions, list)

    def test_generate_report_empty(self):
        from code4u.agents.wisdom_agent import WisdomAgent
        agent = WisdomAgent()
        report = agent.generate_report([])
        assert "No relevant historical fixes" in report

    def test_suggestion_to_dict_camel_case(self):
        from code4u.agents.wisdom_agent import WisdomSuggestion
        s = WisdomSuggestion(
            file_path="a.py", issue_description="test", suggested_fix="fix",
            confidence=0.9, source_nugget_id="n1", source_project="p1",
            pattern_type="bug_fix", language="python",
        )
        d = s.to_dict()
        assert "filePath" in d
        assert "issueDescription" in d
        assert "suggestedFix" in d

    def test_duplicate_candidate_to_dict(self):
        from code4u.agents.wisdom_agent import DuplicateCandidate
        d = DuplicateCandidate(
            function_name="foo", file_path="a.py", project="p1",
            similarity=0.9, original_function="bar", original_project="p2",
            original_file="b.py", recommendation="import instead",
        )
        assert "functionName" in d.to_dict()


# ═══════════════════════════════════════════════════════════════
# Day 20: Legal, License & Ethical Governance
# ═══════════════════════════════════════════════════════════════

class TestLegalAgent:
    """Unit tests for LegalAgent (legal_agent.py)."""

    def test_gpl_to_mit_incompatible(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        result = agent.check_compatibility("GPL-3.0", "MIT")
        assert result.compatible is False

    def test_mit_to_gpl_compatible(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        result = agent.check_compatibility("MIT", "GPL-3.0")
        assert result.compatible is True

    def test_gpl_to_proprietary_incompatible(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        result = agent.check_compatibility("GPL-3.0", "Proprietary")
        assert result.compatible is False

    def test_mit_to_apache_compatible(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        result = agent.check_compatibility("MIT", "Apache-2.0")
        assert result.compatible is True

    def test_agpl_to_proprietary_incompatible(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        result = agent.check_compatibility("AGPL-3.0", "Proprietary")
        assert result.compatible is False

    def test_permissive_to_permissive_compatible(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        result = agent.check_compatibility("BSD-3-Clause", "ISC")
        assert result.compatible is True

    def test_lgpl_to_proprietary_incompatible(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        result = agent.check_compatibility("LGPL-3.0", "Proprietary")
        assert result.compatible is False

    def test_unknown_to_anything_incompatible(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        result = agent.check_compatibility("UnknownLicense", "MIT")
        assert result.compatible is False

    def test_gate_wisdom_transfer_blocks_gpl(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        allowed, violation = agent.gate_wisdom_transfer("GPL-3.0", "Proprietary", nugget_id="n1")
        assert allowed is False
        assert violation is not None
        assert violation.blocked is True

    def test_gate_wisdom_transfer_allows_mit(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        allowed, violation = agent.gate_wisdom_transfer("MIT", "Apache-2.0", nugget_id="n2")
        assert allowed is True
        assert violation is None

    def test_normalize_license_aliases(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        assert agent._normalize_license("mit") == "MIT"
        assert agent._normalize_license("gpl3") == "GPL-3.0"
        assert agent._normalize_license("apache 2.0") == "Apache-2.0"
        assert agent._normalize_license("bsd") == "BSD-3-Clause"
        assert agent._normalize_license("proprietary") == "Proprietary"

    def test_detect_license_from_content_mit(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        content = "MIT License\n\nPermission is hereby granted, free of charge..."
        info = agent.detect_license_from_content(content, "LICENSE")
        assert info.license_id == "MIT"

    def test_detect_license_from_content_gpl(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        content = "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007"
        info = agent.detect_license_from_content(content, "COPYING")
        assert info.license_id == "GPL-3.0"

    def test_detect_license_from_package_json(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        content = json.dumps({"name": "my-pkg", "license": "Apache-2.0"})
        info = agent.detect_license_from_content(content, "package.json")
        assert info.license_id == "Apache-2.0"

    def test_compatibility_result_to_dict(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        result = agent.check_compatibility("MIT", "MIT")
        d = result.to_dict()
        assert "compatible" in d
        assert "sourceLicense" in d
        assert "targetLicense" in d
        assert "reason" in d

    def test_get_compatibility_matrix(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        matrix = agent.get_compatibility_matrix()
        assert "categories" in matrix
        assert "matrix" in matrix
        assert len(matrix["categories"]) == 4

    def test_violations_list_tracks_blocked(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        agent.gate_wisdom_transfer("GPL-3.0", "MIT", nugget_id="v1")
        agent.gate_wisdom_transfer("AGPL-3.0", "Proprietary", nugget_id="v2")
        violations = agent.get_violations()
        assert len(violations) == 2
        assert all(v.blocked for v in violations)

    def test_generate_report_includes_violations(self):
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        agent.gate_wisdom_transfer("GPL-3.0", "MIT", nugget_id="r1")
        report = agent.generate_report()
        assert "License" in report
        assert "Violation" in report or "violation" in report

    def test_license_info_to_dict(self):
        from code4u.agents.legal_agent import LicenseInfo, LicenseCategory
        info = LicenseInfo("MIT", "MIT", LicenseCategory.PERMISSIVE, False, "LICENSE", 0.95)
        d = info.to_dict()
        assert d["licenseId"] == "MIT"
        assert d["category"] == "permissive"
        assert d["copyleft"] is False

    def test_singleton_legal_agent(self):
        from code4u.agents.legal_agent import get_legal_agent
        import code4u.agents.legal_agent as mod
        mod._legal_agent_singleton = None
        a = get_legal_agent()
        b = get_legal_agent()
        assert a is b


class TestProvenanceTracker:
    """Unit tests for ProvenanceTracker (provenance_tracker.py)."""

    def test_record_attribution_creates_record(self):
        from code4u.knowledge.provenance_tracker import ProvenanceTracker
        tracker = ProvenanceTracker()
        rec = tracker.record_attribution("app.py", "Fixed XSS", source_type="wisdom_nugget")
        assert rec.record_id
        assert rec.file_path == "app.py"
        assert rec.applied is False

    def test_mark_applied(self):
        from code4u.knowledge.provenance_tracker import ProvenanceTracker
        tracker = ProvenanceTracker()
        rec = tracker.record_attribution("a.py", "fix")
        assert tracker.mark_applied(rec.record_id) is True
        applied_records = tracker.get_records(applied_only=True)
        assert len(applied_records) >= 1
        assert applied_records[0].applied is True

    def test_mark_applied_nonexistent_returns_false(self):
        from code4u.knowledge.provenance_tracker import ProvenanceTracker
        tracker = ProvenanceTracker()
        assert tracker.mark_applied("nonexistent") is False

    def test_export_attribution_json(self):
        from code4u.knowledge.provenance_tracker import ProvenanceTracker
        tracker = ProvenanceTracker()
        rec = tracker.record_attribution("a.py", "fix", source_nugget_id="n1")
        tracker.mark_applied(rec.record_id)
        content = tracker.export_attribution_json("/tmp/project")
        data = json.loads(content)
        assert data["schemaVersion"] == "1.0"
        assert data["totalAttributions"] == 1
        assert len(data["attributions"]) == 1

    def test_get_stats(self):
        from code4u.knowledge.provenance_tracker import ProvenanceTracker
        tracker = ProvenanceTracker()
        tracker.record_attribution("a.py", "fix1", source_type="wisdom_nugget", license_verified=True)
        tracker.record_attribution("b.py", "fix2", source_type="ai_generation")
        stats = tracker.get_stats()
        assert stats["totalRecords"] == 2
        assert stats["licenseVerified"] == 1
        assert "wisdom_nugget" in stats["bySourceType"]

    def test_clear_empties_records(self):
        from code4u.knowledge.provenance_tracker import ProvenanceTracker
        tracker = ProvenanceTracker()
        tracker.record_attribution("a.py", "fix")
        tracker.record_attribution("b.py", "fix")
        count = tracker.clear()
        assert count == 2
        assert len(tracker.get_records()) == 0

    def test_to_dict_camel_case(self):
        from code4u.knowledge.provenance_tracker import ProvenanceTracker
        tracker = ProvenanceTracker()
        rec = tracker.record_attribution("a.py", "fix")
        d = rec.to_dict()
        assert "recordId" in d
        assert "filePath" in d
        assert "sourceType" in d
        assert "licenseVerified" in d


class TestToxicScanner:
    """Unit tests for ToxicScanner (toxic_scanner.py)."""

    def test_detects_googlebot_spoofing(self):
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        scanner = ToxicScanner()
        # Pattern matches User-Agent = "Googlebot" or User-Agent: "Googlebot"
        matches = scanner.scan_text('User-Agent = "Googlebot"')
        assert len(matches) > 0
        assert any(m.pattern_name == "unauthorized_scraping_headers" for m in matches)

    def test_detects_race_based_logic(self):
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        scanner = ToxicScanner()
        matches = scanner.scan_text('if race == "white": discount = 10')
        assert any(m.category == "bias" for m in matches)

    def test_detects_crypto_mining(self):
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        scanner = ToxicScanner()
        matches = scanner.scan_text("connect to stratum+tcp://pool.mining.org:3333")
        assert any(m.pattern_name == "crypto_mining_stealth" for m in matches)

    def test_detects_encoded_eval_backdoor(self):
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        scanner = ToxicScanner()
        matches = scanner.scan_text("eval(atob(encoded_payload))")
        assert any(m.pattern_name == "backdoor_eval" for m in matches)

    def test_clean_code_no_matches(self):
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        scanner = ToxicScanner()
        matches = scanner.scan_text("def add(a, b):\n    return a + b\n")
        assert len(matches) == 0

    def test_has_blocking_matches(self):
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        scanner = ToxicScanner()
        matches = scanner.scan_text("connect to stratum+tcp://pool.mining.org")
        assert scanner.has_blocking_matches(matches) is True

    def test_add_custom_pattern(self):
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        scanner = ToxicScanner()
        scanner.add_custom_pattern("internal_api", r"internal\.corp\.api", category="custom", severity="high", blocked=True)
        matches = scanner.scan_text("url = internal.corp.api/v1/secret")
        assert any(m.pattern_name == "internal_api" for m in matches)

    def test_scan_multiple_files(self):
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        scanner = ToxicScanner()
        matches = scanner.scan_code({
            "a.py": 'User-Agent = "Googlebot"',
            "b.py": "def clean(): pass",
        })
        assert any(m.file_path == "a.py" for m in matches)
        assert not any(m.file_path == "b.py" for m in matches)

    def test_get_stats(self):
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        scanner = ToxicScanner()
        scanner.scan_text("eval(atob(x))")
        stats = scanner.get_stats()
        assert stats["totalMatches"] >= 1
        assert "byCategory" in stats
        assert "bySeverity" in stats

    def test_clear_resets(self):
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        scanner = ToxicScanner()
        scanner.scan_text("eval(atob(x))")
        count = scanner.clear()
        assert count >= 1
        assert len(scanner.get_all_matches()) == 0

    def test_generate_report(self):
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        scanner = ToxicScanner()
        scanner.scan_text("eval(atob(x))")
        report = scanner.generate_report()
        assert "Toxic" in report
        assert "backdoor" in report.lower() or "BLOCKED" in report

    def test_match_to_dict_camel_case(self):
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        scanner = ToxicScanner()
        matches = scanner.scan_text("eval(atob(x))")
        if matches:
            d = matches[0].to_dict()
            assert "matchId" in d
            assert "patternName" in d
            assert "filePath" in d


# ═══════════════════════════════════════════════════════════════
# Day 21: Final Optimization
# ═══════════════════════════════════════════════════════════════

class TestInMemoryLRUCache:
    """Unit tests for InMemoryLRUCache (core/cache.py)."""

    def test_set_and_get(self):
        from code4u.core.cache import InMemoryLRUCache
        cache = InMemoryLRUCache()
        cache.set("k1", {"value": 42})
        assert cache.get("k1") == {"value": 42}

    def test_get_miss_returns_none(self):
        from code4u.core.cache import InMemoryLRUCache
        cache = InMemoryLRUCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self):
        from code4u.core.cache import InMemoryLRUCache
        cache = InMemoryLRUCache(default_ttl=0.01)
        cache.set("k1", "value")
        time.sleep(0.02)
        assert cache.get("k1") is None

    def test_max_size_eviction(self):
        from code4u.core.cache import InMemoryLRUCache
        cache = InMemoryLRUCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_lru_order(self):
        from code4u.core.cache import InMemoryLRUCache
        cache = InMemoryLRUCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # touch a -> a is now most recent
        cache.set("d", 4)  # evicts b (least recently used)
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_delete(self):
        from code4u.core.cache import InMemoryLRUCache
        cache = InMemoryLRUCache()
        cache.set("k1", "val")
        assert cache.delete("k1") is True
        assert cache.get("k1") is None
        assert cache.delete("k1") is False

    def test_clear(self):
        from code4u.core.cache import InMemoryLRUCache
        cache = InMemoryLRUCache()
        cache.set("a", 1)
        cache.set("b", 2)
        count = cache.clear()
        assert count == 2
        assert cache.size() == 0

    def test_stats(self):
        from code4u.core.cache import InMemoryLRUCache
        cache = InMemoryLRUCache(max_size=100)
        cache.set("a", 1)
        cache.get("a")
        cache.get("missing")
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hitRate"] == 0.5
        assert stats["size"] == 1

    def test_cleanup_expired(self):
        from code4u.core.cache import InMemoryLRUCache
        cache = InMemoryLRUCache(default_ttl=0.01)
        cache.set("a", 1)
        cache.set("b", 2)
        time.sleep(0.02)
        removed = cache.cleanup_expired()
        assert removed == 2


class TestRedisCacheManager:
    """Unit tests for RedisCacheManager (core/cache.py) — memory-only mode."""

    def test_set_and_get_memory(self):
        from code4u.core.cache import RedisCacheManager
        cache = RedisCacheManager(redis_url="")
        cache.set("legal", {"compatible": True}, "MIT", "Apache")
        val = cache.get("legal", "MIT", "Apache")
        assert val == {"compatible": True}

    def test_get_miss(self):
        from code4u.core.cache import RedisCacheManager
        cache = RedisCacheManager(redis_url="")
        assert cache.get("legal", "nonexistent") is None

    def test_delete(self):
        from code4u.core.cache import RedisCacheManager
        cache = RedisCacheManager(redis_url="")
        cache.set("test", "val", "key1")
        assert cache.delete("test", "key1") is True

    def test_invalidate_namespace(self):
        from code4u.core.cache import RedisCacheManager
        cache = RedisCacheManager(redis_url="")
        cache.set("legal", "v1", "k1")
        cache.set("legal", "v2", "k2")
        cache.set("wisdom", "v3", "k3")
        count = cache.invalidate_namespace("legal")
        assert count == 2

    def test_clear_all(self):
        from code4u.core.cache import RedisCacheManager
        cache = RedisCacheManager(redis_url="")
        cache.set("a", 1, "k1")
        cache.set("b", 2, "k2")
        count = cache.clear_all()
        assert count >= 2

    def test_stats(self):
        from code4u.core.cache import RedisCacheManager
        cache = RedisCacheManager(redis_url="")
        stats = cache.get_stats()
        assert stats["backend"] == "memory"
        assert stats["redisAvailable"] is False

    def test_default_ttls_configured(self):
        from code4u.core.cache import RedisCacheManager
        assert RedisCacheManager.DEFAULT_TTLS["legal"] == 86400.0
        assert RedisCacheManager.DEFAULT_TTLS["wisdom"] == 3600.0
        assert RedisCacheManager.DEFAULT_TTLS["toxic"] == 43200.0


class TestPartitionedVectorStore:
    """Unit tests for PartitionedVectorStore (vector_store.py)."""

    def test_create_partition(self):
        from code4u.ai_engine.vector_store import PartitionedVectorStore
        pvs = PartitionedVectorStore()
        p = pvs.get_partition("tenant-1")
        assert p is not None

    def test_add_to_partition(self):
        from code4u.ai_engine.vector_store import PartitionedVectorStore, VectorDocument
        pvs = PartitionedVectorStore()
        count = pvs.add_to_partition("t1", [VectorDocument(id="d1", content="hello world")])
        assert count == 1

    def test_add_to_global(self):
        from code4u.ai_engine.vector_store import PartitionedVectorStore, VectorDocument
        pvs = PartitionedVectorStore()
        count = pvs.add_to_global([VectorDocument(id="g1", content="fix SQL injection")])
        assert count == 1

    def test_search_partition(self):
        from code4u.ai_engine.vector_store import PartitionedVectorStore, VectorDocument
        pvs = PartitionedVectorStore()
        pvs.add_to_partition("t1", [VectorDocument(id="d1", content="hello world greeting")])
        results = pvs.search_partition("t1", "hello greeting", top_k=5)
        assert len(results) >= 1

    def test_search_global(self):
        from code4u.ai_engine.vector_store import PartitionedVectorStore, VectorDocument
        pvs = PartitionedVectorStore()
        pvs.add_to_global([VectorDocument(id="g1", content="fix SQL injection parameterized")])
        results = pvs.search_global("SQL injection", top_k=5)
        assert len(results) >= 1

    def test_partition_isolation(self):
        from code4u.ai_engine.vector_store import PartitionedVectorStore, VectorDocument
        pvs = PartitionedVectorStore()
        pvs.add_to_partition("t1", [VectorDocument(id="d1", content="project alpha code")])
        pvs.add_to_partition("t2", [VectorDocument(id="d2", content="project beta code")])
        r1 = pvs.search_partition("t1", "alpha", top_k=5)
        r2 = pvs.search_partition("t2", "alpha", top_k=5)
        assert len(r1) >= 1
        assert all(r.id == "d1" or r.id.startswith("d1") for r in r1)

    def test_remove_partition(self):
        from code4u.ai_engine.vector_store import PartitionedVectorStore, VectorDocument
        pvs = PartitionedVectorStore()
        pvs.add_to_partition("t1", [VectorDocument(id="d1", content="temp")])
        assert pvs.remove_partition("t1") is True
        assert pvs.remove_partition("nonexistent") is False

    def test_stats(self):
        from code4u.ai_engine.vector_store import PartitionedVectorStore, VectorDocument
        pvs = PartitionedVectorStore()
        pvs.add_to_partition("t1", [VectorDocument(id="d1", content="a")])
        pvs.add_to_global([VectorDocument(id="g1", content="b")])
        stats = pvs.stats()
        assert stats["totalDocuments"] == 2
        assert stats["partitionCount"] == 1

    def test_clear_all(self):
        from code4u.ai_engine.vector_store import PartitionedVectorStore, VectorDocument
        pvs = PartitionedVectorStore()
        pvs.add_to_partition("t1", [VectorDocument(id="d1", content="a")])
        pvs.add_to_global([VectorDocument(id="g1", content="b")])
        count = pvs.clear_all()
        assert count == 2
