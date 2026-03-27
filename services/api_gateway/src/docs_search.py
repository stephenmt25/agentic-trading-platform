"""Documentation search for RAG chatbot.

Uses Viking for semantic search, then reads source markdown files directly
from disk (avoiding the slow Viking read subprocess per chunk).
"""

import asyncio
import os
import re
from dataclasses import dataclass
from typing import Optional

from libs.observability import get_logger

logger = get_logger("api-gateway.docs-search")

# Resolve paths relative to the project root (services/api_gateway/src/ → 3 levels up)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_VIKING_SCRIPT = os.path.join(_PROJECT_ROOT, "viking.py")
_VIKING_CONFIG = os.path.join(_PROJECT_ROOT, "ov.conf")
_DOCS_DIR = os.path.join(_PROJECT_ROOT, "docs")

# Regex to parse Viking search output:
#   [0.6071] viking://resources/docs/risk-management/.../Circuit_Breakers.md
#            This technical reference document details...
_RESULT_RE = re.compile(r'^\s*\[(\d+\.\d+)\]\s+(viking://\S+)\s*$')
_SNIPPET_RE = re.compile(r'^\s{2,}(\S.+)$')


@dataclass
class SearchResult:
    uri: str
    score: float
    snippet: str
    doc_path: Optional[str] = None  # resolved local file path


def _uri_to_doc_file(uri: str) -> Optional[str]:
    """Map a Viking URI to the source markdown file on disk.

    Viking URIs look like:
      viking://resources/docs/risk-management/.../Circuit_Breakers.md
      viking://resources/docs/modules/hot-path/Hot-Path_Processor/...
      viking://resources/docs/agent-architecture/...

    We extract the path segments after 'docs/' and try to find the matching .md file.
    """
    # Extract everything after 'docs/'
    m = re.search(r'viking://resources/docs/(.+)', uri)
    if not m:
        return None
    segments = m.group(1).split("/")

    # Try progressively longer paths: docs/seg1.md, docs/seg1/seg2.md, etc.
    for depth in range(min(3, len(segments)), 0, -1):
        path_parts = segments[:depth]
        candidate = os.path.join(_DOCS_DIR, *path_parts[:-1], f"{path_parts[-1]}.md") if depth > 1 else os.path.join(_DOCS_DIR, f"{path_parts[0]}.md")
        if os.path.isfile(candidate):
            return candidate

    # Try first segment as directory name, look for .md in docs/
    first = segments[0]
    direct = os.path.join(_DOCS_DIR, f"{first}.md")
    if os.path.isfile(direct):
        return direct

    # Try modules/first.md
    if len(segments) >= 2:
        modules_path = os.path.join(_DOCS_DIR, segments[0], f"{segments[1]}.md")
        if os.path.isfile(modules_path):
            return modules_path

    return None


def uri_to_doc_slug(uri: str) -> Optional[str]:
    """Convert a Viking URI to a docs page slug for frontend links.

    viking://resources/docs/risk-management/... -> risk-management
    viking://resources/docs/modules/hot-path/... -> modules/hot-path
    """
    # Check for modules path
    m = re.search(r'viking://resources/docs/modules/([^/]+)', uri)
    if m:
        return f"modules/{m.group(1)}"

    m = re.search(r'viking://resources/docs/([^/]+)', uri)
    if m:
        return m.group(1)
    return None


async def _run_viking_search(query: str, timeout: float = 45.0) -> str:
    """Run viking.py search and return stdout."""
    env = os.environ.copy()
    env["OPENVIKING_CONFIG_FILE"] = _VIKING_CONFIG

    cmd = ["python", _VIKING_SCRIPT, "search", query]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=_PROJECT_ROOT,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        logger.warning("Viking search timed out", query=query)
        return ""
    except Exception as e:
        logger.error("Viking search failed", error=str(e))
        return ""


def _read_doc_file(path: str, max_chars: int = 4000) -> str:
    """Read a markdown file from disk, truncated to max_chars."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read(max_chars)
        return content
    except Exception as e:
        logger.warning("Failed to read doc file", path=path, error=str(e))
        return ""


async def search_docs(query: str, top_k: int = 5) -> list[SearchResult]:
    """Search documentation using Viking and return results with file content."""
    raw = await _run_viking_search(query)

    results: list[SearchResult] = []
    current_uri: Optional[str] = None
    current_score: float = 0.0

    for line in raw.splitlines():
        m = _RESULT_RE.match(line)
        if m:
            if current_uri:
                doc_path = _uri_to_doc_file(current_uri)
                results.append(SearchResult(
                    uri=current_uri, score=current_score, snippet="", doc_path=doc_path,
                ))
            current_score = float(m.group(1))
            current_uri = m.group(2)
            continue

        sm = _SNIPPET_RE.match(line)
        if sm and current_uri:
            snippet = sm.group(1).strip()
            doc_path = _uri_to_doc_file(current_uri)
            results.append(SearchResult(
                uri=current_uri, score=current_score, snippet=snippet, doc_path=doc_path,
            ))
            current_uri = None

    if current_uri:
        doc_path = _uri_to_doc_file(current_uri)
        results.append(SearchResult(
            uri=current_uri, score=current_score, snippet="", doc_path=doc_path,
        ))

    # Deduplicate by doc file (multiple chunks may point to same doc)
    seen_paths: set[str] = set()
    deduped: list[SearchResult] = []
    for r in results:
        key = r.doc_path or r.uri
        if key not in seen_paths:
            seen_paths.add(key)
            deduped.append(r)
        if len(deduped) >= top_k:
            break

    return deduped


def read_doc_content(result: SearchResult, max_chars: int = 4000) -> str:
    """Read the actual markdown content for a search result from disk."""
    if result.doc_path:
        return _read_doc_file(result.doc_path, max_chars)
    return ""
