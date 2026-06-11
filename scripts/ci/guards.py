#!/usr/bin/env python3
"""CI guards mirroring the local Claude-Code hooks (EN-W0, 2026-06-11).

Two repo-wide, AST-based blocking gates:

1. **Float guard** — no ``float(`` calls in the financial services
   (``services/execution``, ``services/pnl``, ``services/risk``,
   ``services/strategy``). A call is exempt when any source line spanned by
   the call carries a ``# float-ok`` marker — markers often sit on the
   closing-paren line after black wraps a call, so the whole
   ``lineno..end_lineno`` span is checked, not just the first line.

2. **Channel guard** — every ``stream:*`` / ``pubsub:*`` string literal in
   tracked Python code must exactly match a channel declared as a
   module-level string constant in ``libs/messaging/channels.py``.
   Docstrings are skipped (they may describe planned channels); exact
   membership is required, so prefixes of real channel names fail (the
   local hook's substring containment let those through).

AST-based on purpose: comments, docstrings and ``_to_float(`` can't false-
positive, unlike the grep in the local hooks. Stdlib only — runs identically
under pre-commit and CI.

Exit 0 when clean; exit 1 with ``file:line`` listings on any violation.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHANNELS_FILE = Path("libs/messaging/channels.py")
FLOAT_GUARD_DIRS = (
    "services/execution/",
    "services/pnl/",
    "services/risk/",
    "services/strategy/",
    # EN-W1: the shared exit policy is live financial decision logic; the
    # backtest engines must stay Decimal-exact on trade mechanics too (their
    # indicator/numpy float use carries explicit '# float-ok' markers).
    "libs/core/exit_policy.py",
    "services/backtesting/",
)
FLOAT_OK_MARKER = "# float-ok"
CHANNEL_TOKEN_RE = re.compile(r"(?:stream:|pubsub:)[a-z_]+")
CHANNEL_NAME_RE = re.compile(r"^(?:stream:|pubsub:)[a-z_]+$")


def tracked_py_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [Path(line) for line in out.stdout.splitlines() if line]


def canonical_channels() -> set[str]:
    """Channel names declared as module-level string constants."""
    tree = ast.parse((REPO_ROOT / CHANNELS_FILE).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            value = node.value.value
            if isinstance(value, str) and CHANNEL_NAME_RE.match(value):
                names.add(value)
    return names


def docstring_constant_ids(tree: ast.AST) -> set[int]:
    """``id()`` of every Constant node that is a docstring."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def check_floats(rel_path: Path, tree: ast.AST, lines: list[str]) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "float"
        ):
            first = node.lineno
            last = node.end_lineno or node.lineno
            span_marked = any(
                FLOAT_OK_MARKER in lines[i - 1]
                for i in range(first, last + 1)
                if 0 < i <= len(lines)
            )
            if span_marked:
                continue
            violations.append(
                f"{rel_path}:{first}: float() in a financial code path — use "
                "Decimal (libs/core/types.py), or add '# float-ok: <reason>' "
                "on the call if the value is genuinely non-monetary"
            )
    return violations


def check_channels(rel_path: Path, tree: ast.AST, channels: set[str]) -> list[str]:
    violations: list[str] = []
    skip_ids = docstring_constant_ids(tree)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in skip_ids
        ):
            for token in CHANNEL_TOKEN_RE.findall(node.value):
                if token not in channels:
                    violations.append(
                        f"{rel_path}:{node.lineno}: unknown channel '{token}' — "
                        f"channels must be declared in {CHANNELS_FILE.as_posix()}"
                    )
    return violations


def main() -> int:
    channels = canonical_channels()
    if not channels:
        print(f"FATAL: no channels parsed from {CHANNELS_FILE}", file=sys.stderr)
        return 1

    self_rel = Path(__file__).resolve().relative_to(REPO_ROOT)
    violations: list[str] = []
    for rel_path in tracked_py_files():
        if rel_path == CHANNELS_FILE or rel_path == self_rel:
            continue
        full = REPO_ROOT / rel_path
        try:
            source = full.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            # Unparsable files are some other gate's problem; don't mask the
            # guard result behind them, but do say something.
            print(f"WARN: skipped {rel_path}: {exc}", file=sys.stderr)
            continue

        if str(rel_path.as_posix()).startswith(FLOAT_GUARD_DIRS):
            violations += check_floats(rel_path, tree, source.splitlines())
        violations += check_channels(rel_path, tree, channels)

    if violations:
        print(f"GUARDS FAILED — {len(violations)} violation(s):\n")
        print("\n".join(violations))
        return 1

    print(f"guards OK ({len(channels)} canonical channels)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
