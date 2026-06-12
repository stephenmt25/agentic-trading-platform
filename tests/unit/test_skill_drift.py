"""Tests for the agent skill-bundle pipeline (TECH-DEBT-REGISTRY row 36).

Covers scripts/sync_agent_skills.py (idempotent, deterministic bundle sync)
and scripts/ci/check_skill_drift.py (CI gate failing on any divergence between
canonical prompts/skills/*.md and bundled/inlined copies), plus a live check
that THIS repo is in the synced state.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for extra in (REPO_ROOT / "scripts", REPO_ROOT / "scripts" / "ci"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import check_skill_drift  # noqa: E402
import sync_agent_skills  # noqa: E402

CANONICAL_SKILL = "Hello {{name}}, stay advisory.\nSecond canonical line.\n"


def make_repo(tmp_path: Path) -> Path:
    """A miniature repo with one skill, one bundle target, one inline consumer."""
    skills = tmp_path / "prompts" / "skills"
    skills.mkdir(parents=True)
    (skills / "greeting.md").write_text(CANONICAL_SKILL, encoding="utf-8")
    manifest = {
        "bundles": {"svc_a": ["greeting"]},
        "inline_consumers": {"inline/consumer.txt": ["greeting"]},
    }
    (skills / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    inline = tmp_path / "inline"
    inline.mkdir()
    (inline / "consumer.txt").write_text(
        "prefix\nHello Bob, stay advisory.\nSecond canonical line.\nsuffix\n",
        encoding="utf-8",
    )
    (tmp_path / "services").mkdir()
    return tmp_path


class TestSync:
    def test_sync_creates_bundle_with_header(self, tmp_path):
        root = make_repo(tmp_path)
        changed = sync_agent_skills.sync(root)
        bundle = root / "services" / "svc_a" / "prompts" / "skills" / "greeting.md"
        assert changed == [bundle]
        content = bundle.read_text(encoding="utf-8")
        assert content.startswith("<!-- AUTO-GENERATED")
        assert content.endswith(CANONICAL_SKILL)
        assert "prompts/skills/greeting.md" in content

    def test_sync_is_idempotent(self, tmp_path):
        root = make_repo(tmp_path)
        first = sync_agent_skills.sync(root)
        assert len(first) == 1
        bundle_bytes = first[0].read_bytes()
        second = sync_agent_skills.sync(root)
        assert second == []  # nothing rewritten
        assert first[0].read_bytes() == bundle_bytes

    def test_sync_rewrites_after_canonical_change(self, tmp_path):
        root = make_repo(tmp_path)
        sync_agent_skills.sync(root)
        skill = root / "prompts" / "skills" / "greeting.md"
        skill.write_text(CANONICAL_SKILL + "Third line.\n", encoding="utf-8")
        changed = sync_agent_skills.sync(root)
        assert len(changed) == 1
        assert "Third line." in changed[0].read_text(encoding="utf-8")

    def test_dry_run_writes_nothing(self, tmp_path):
        root = make_repo(tmp_path)
        changed = sync_agent_skills.sync(root, dry_run=True)
        assert len(changed) == 1
        assert not changed[0].exists()


class TestCheck:
    def test_clean_after_sync(self, tmp_path):
        root = make_repo(tmp_path)
        sync_agent_skills.sync(root)
        assert check_skill_drift.check(root) == []

    def test_missing_bundle_fails(self, tmp_path):
        root = make_repo(tmp_path)  # no sync run
        failures = check_skill_drift.check(root)
        assert any("bundle missing" in f for f in failures)

    def test_edited_bundle_fails(self, tmp_path):
        root = make_repo(tmp_path)
        (bundle,) = sync_agent_skills.sync(root)
        bundle.write_text(
            bundle.read_text(encoding="utf-8") + "hand edit\n", encoding="utf-8"
        )
        failures = check_skill_drift.check(root)
        assert any("bundle drift" in f for f in failures)

    def test_canonical_change_without_resync_fails(self, tmp_path):
        root = make_repo(tmp_path)
        sync_agent_skills.sync(root)
        skill = root / "prompts" / "skills" / "greeting.md"
        skill.write_text(CANONICAL_SKILL + "New canonical line.\n", encoding="utf-8")
        failures = check_skill_drift.check(root)
        assert any("bundle drift" in f for f in failures)
        # inline consumer also lacks the new concrete line
        assert any("inline drift" in f for f in failures)

    def test_inline_drift_fails(self, tmp_path):
        root = make_repo(tmp_path)
        sync_agent_skills.sync(root)
        consumer = root / "inline" / "consumer.txt"
        consumer.write_text(
            "prefix\nHello Bob, stay advisory.\nsuffix\n", encoding="utf-8"
        )
        failures = check_skill_drift.check(root)
        assert any(
            "inline drift" in f and "Second canonical line." in f for f in failures
        )

    def test_stale_bundle_fails(self, tmp_path):
        root = make_repo(tmp_path)
        sync_agent_skills.sync(root)
        stray = root / "services" / "svc_a" / "prompts" / "skills" / "orphan.md"
        stray.write_text("not in manifest\n", encoding="utf-8")
        failures = check_skill_drift.check(root)
        assert any("stale bundle" in f for f in failures)

    def test_placeholder_segments_match_any_text(self, tmp_path):
        root = make_repo(tmp_path)
        sync_agent_skills.sync(root)
        # "Hello {{name}}, stay advisory." must match "Hello Anyone At All, ..."
        consumer = root / "inline" / "consumer.txt"
        consumer.write_text(
            "Hello Anyone At All, stay advisory.\nSecond canonical line.\n",
            encoding="utf-8",
        )
        assert check_skill_drift.check(root) == []


class TestLinePattern:
    def test_placeholder_only_line_is_skipped(self):
        assert check_skill_drift.line_pattern("{{headlines}}") is None
        assert check_skill_drift.line_pattern("   ") is None
        assert check_skill_drift.line_pattern("{{a}}{{b}}") is None

    def test_literal_line_requires_exact_text(self):
        pat = check_skill_drift.line_pattern("Exact literal.")
        assert pat is not None
        assert pat.search("xx Exact literal. yy")
        assert not pat.search("Exact literal mutated.")

    def test_json_braces_are_not_placeholders(self):
        line = 'Respond with exactly: {"score": <float -1.0 to 1.0>}'
        pat = check_skill_drift.line_pattern(line)
        assert pat is not None
        assert pat.search('a\nRespond with exactly: {"score": <float -1.0 to 1.0>}\nb')
        assert not pat.search('Respond with exactly: {"score": 1}')


class TestRealRepo:
    """The actual working tree must be in the synced, drift-free state."""

    def test_repo_is_in_synced_state(self):
        failures = check_skill_drift.check(REPO_ROOT)
        assert failures == [], "\n".join(failures)

    def test_repo_sync_is_noop(self):
        changed = sync_agent_skills.sync(REPO_ROOT, dry_run=True)
        assert changed == [], [str(p) for p in changed]
