#!/usr/bin/env python3
"""
viking.py — Helper script for OpenViking CLI operations.

Usage:
    python viking.py search "query"
    python viking.py abstract viking://resources/...
    python viking.py overview viking://resources/...
    python viking.py read viking://resources/...
    python viking.py ls [viking://resources/...]
    python viking.py load ./path/to/file_or_dir
    python viking.py status
    python viking.py glob "**/*.md"
    python viking.py reindex                          # Clean reindex of docs
"""
import sys
import os
import openviking as ov

VIKING_DATA_PATH = "./viking-data"


def get_client():
    client = ov.SyncOpenViking(path=VIKING_DATA_PATH)
    client.initialize()
    return client


def cmd_search(query, target_uri=None):
    client = get_client()
    kwargs = {"query": query}
    if target_uri:
        kwargs["target_uri"] = target_uri
    results = client.find(**kwargs)
    for r in results.resources:
        print(f"  [{r.score:.4f}] {r.uri}")
        if hasattr(r, "abstract") and r.abstract:
            print(f"           {r.abstract[:120]}...")
    client.close()


def cmd_abstract(uri):
    client = get_client()
    result = client.abstract(uri)
    print(result)
    client.close()


def cmd_overview(uri):
    client = get_client()
    result = client.overview(uri)
    print(result)
    client.close()


def cmd_read(uri):
    client = get_client()
    result = client.read(uri)
    print(result)
    client.close()


def cmd_ls(uri=None):
    client = get_client()
    target = uri or "viking://resources/"
    result = client.ls(target)
    if isinstance(result, list):
        for entry in result:
            prefix = "[DIR] " if entry.get("isDir") else "      "
            print(f"{prefix}{entry.get('name', '?'):<50} {entry.get('uri', '')}")
    else:
        print(result)
    client.close()


def cmd_load(path):
    client = get_client()
    print(f"Loading: {path}")
    result = client.add_resource(path=path)
    root_uri = result.get("root_uri", "unknown")
    print(f"Loaded as: {root_uri}")
    print("Waiting for processing...")
    client.wait_processed()
    print("Done.")
    client.close()


def cmd_status():
    client = get_client()
    result = client.ls("viking://resources/")
    if isinstance(result, list):
        print(f"Indexed resources ({len(result)}):")
        for entry in result:
            prefix = "[DIR] " if entry.get("isDir") else "      "
            print(f"  {prefix}{entry.get('name', '?')}")
    else:
        print(result)
    client.close()


def cmd_glob(pattern):
    client = get_client()
    results = client.find(query=pattern)
    for r in results.resources:
        print(r.uri)
    client.close()


def cmd_reindex():
    """Clean reindex: remove old resources via API, then reload docs."""
    docs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    if not os.path.isdir(docs_path):
        print(f"ERROR: docs directory not found at {docs_path}")
        sys.exit(1)

    client = get_client()

    # Remove all existing resources to eliminate duplicates (docs, docs_1, docs_2, etc.)
    entries = client.ls("viking://resources/")
    if isinstance(entries, list):
        dirs = [e for e in entries if e.get("isDir")]
        if dirs:
            print(f"Removing {len(dirs)} old resource(s)...")
            for d in dirs:
                uri = d.get("uri", "")
                name = d.get("name", "?")
                try:
                    client.remove_resource(uri)
                    print(f"  Removed: {name}")
                except Exception as e:
                    print(f"  Warning: could not remove {name}: {e}")

    # Fresh load
    print(f"Indexing: {docs_path}")
    result = client.add_resource(path=docs_path)
    root_uri = result.get("root_uri", "unknown")
    print(f"Loaded as: {root_uri}")
    print("Waiting for semantic processing (this may take a few minutes on free-tier Gemini)...")
    client.wait_processed()

    # Show result
    entries = client.ls("viking://resources/")
    if isinstance(entries, list):
        dirs = [e for e in entries if e.get("isDir")]
        files = [e for e in entries if not e.get("isDir")]
        print(f"\nReindex complete: {len(dirs)} resource(s), {len(files)} file(s)")
        for d in dirs:
            print(f"  [DIR] {d.get('name')}")
    else:
        print("Reindex complete.")

    client.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "search": lambda: cmd_search(args[0], args[1] if len(args) > 1 else None),
        "abstract": lambda: cmd_abstract(args[0]),
        "overview": lambda: cmd_overview(args[0]),
        "read": lambda: cmd_read(args[0]),
        "ls": lambda: cmd_ls(args[0] if args else None),
        "load": lambda: cmd_load(args[0]),
        "status": lambda: cmd_status(),
        "glob": lambda: cmd_glob(args[0]),
        "reindex": lambda: cmd_reindex(),
    }

    if command not in commands:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)

    commands[command]()


if __name__ == "__main__":
    main()
