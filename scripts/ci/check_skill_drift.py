#!/usr/bin/env python3
"""CI gate: agent skill bundles and inlined skill copies must match canonical.

Companion to ``scripts/sync_agent_skills.py`` (TECH-DEBT-REGISTRY row 36,
pattern: ``anthropics/financial-services`` ``check.py``). Exits non-zero when:

1. A service bundle ``services/<svc>/prompts/skills/<skill>.md`` is missing or
   not byte-identical to the rendered canonical skill (header + content).
2. A bundle file exists under ``services/*/prompts/skills/`` that the manifest
   does not declare (stale/orphaned skill).
3. An ``inline_consumers`` file (prompt template, prompt-loading constant in a
   ``.py`` service file, promptfoo config) no longer carries every concrete
   canonical line of each skill it inlines. ``{{placeholder}}`` segments match
   any text, so templated lines verify their static parts; placeholder-only
   lines are skipped.

Usage:
    python scripts/ci/check_skill_drift.py [--root PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# scripts/ is not a package — make sync_agent_skills importable.
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sync_agent_skills import (  # noqa: E402
    SKILLS_SUBDIR,
    bundle_path,
    load_manifest,
    read_canonical_skill,
    render_bundle,
)

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def line_pattern(line: str) -> re.Pattern | None:
    """Compile one canonical line into a search regex.

    ``{{placeholder}}`` segments become lazy wildcards. Returns ``None`` when
    nothing concrete remains to verify (blank or placeholder-only lines).
    """
    stripped = line.strip()
    if not stripped:
        return None
    # re.split with a capturing group: [literal, name, literal, name, ...]
    parts = _PLACEHOLDER_RE.split(stripped)
    literals = parts[0::2]
    if not any(p.strip() for p in literals):
        return None
    return re.compile(".*?".join(re.escape(p) for p in literals))


def _read_lf(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def check(root: Path) -> list[str]:
    """Return a list of drift failure messages (empty = clean)."""
    failures: list[str] = []
    manifest = load_manifest(root)
    skills_dir = root / SKILLS_SUBDIR

    referenced: set[str] = set()
    for skills in manifest.get("bundles", {}).values():
        referenced.update(skills)
    for skills in manifest.get("inline_consumers", {}).values():
        referenced.update(skills)
    for skill in sorted(referenced):
        if not (skills_dir / f"{skill}.md").exists():
            failures.append(f"canonical skill missing: prompts/skills/{skill}.md")
    if failures:
        return failures

    # 1. Bundles must be byte-identical to the rendered canonical skill.
    for service in sorted(manifest.get("bundles", {})):
        for skill in sorted(manifest["bundles"][service]):
            target = bundle_path(root, service, skill)
            rel = target.relative_to(root).as_posix()
            if not target.exists():
                failures.append(
                    f"bundle missing: {rel} — run scripts/sync_agent_skills.py"
                )
                continue
            expected = render_bundle(skill, read_canonical_skill(root, skill))
            if _read_lf(target) != expected:
                failures.append(
                    f"bundle drift: {rel} differs from prompts/skills/{skill}.md"
                    " — edit the canonical skill and re-run"
                    " scripts/sync_agent_skills.py (never the bundle)"
                )

    # 2. No orphaned bundles outside the manifest.
    for service_dir in sorted((root / "services").glob("*/prompts/skills")):
        service = service_dir.parent.parent.name
        declared = set(manifest.get("bundles", {}).get(service, []))
        for md in sorted(service_dir.glob("*.md")):
            if md.stem not in declared:
                failures.append(
                    f"stale bundle not in manifest: {md.relative_to(root).as_posix()}"
                )

    # 3. Inline consumers must carry every concrete canonical line.
    for consumer, skills in sorted(manifest.get("inline_consumers", {}).items()):
        path = root / consumer
        if not path.exists():
            failures.append(f"inline consumer missing: {consumer}")
            continue
        content = _read_lf(path)
        for skill in sorted(skills):
            canonical = read_canonical_skill(root, skill)
            for line in canonical.splitlines():
                pattern = line_pattern(line)
                if pattern is None:
                    continue
                if not pattern.search(content):
                    failures.append(
                        f"inline drift: {consumer} no longer carries canonical"
                        f" line from prompts/skills/{skill}.md:"
                        f" {line.strip()!r}"
                    )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repo root (default: inferred from this script's location).",
    )
    args = parser.parse_args(argv)

    failures = check(args.root)
    if failures:
        print(f"SKILL DRIFT — {len(failures)} failure(s):\n", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("check_skill_drift OK — bundles and inline skill copies match canonical.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
