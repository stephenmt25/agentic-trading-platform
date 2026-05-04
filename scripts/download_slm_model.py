"""Download the Phi-3-mini GGUF for the local SLM (Track A.2).

The file is ~2.4 GB, so this is a long-running command intentionally
factored out of the AUTONOMOUS execution loop. After the download
completes, uncomment ``PRAXIS_SLM_MODEL_PATH`` in ``.env`` and restart
``services/slm_inference``; ``GET :8095/health`` should report
``"model_loaded": true``.

Usage:
    poetry run python scripts/download_slm_model.py
    poetry run python scripts/download_slm_model.py --variant Phi-3-mini-4k-instruct-q4
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"

DEFAULT_REPO = "microsoft/Phi-3-mini-4k-instruct-gguf"
DEFAULT_FILE = "Phi-3-mini-4k-instruct-q4.gguf"


def parse_args(argv: list | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download a GGUF SLM model into ./models/")
    p.add_argument("--repo", default=DEFAULT_REPO, help="HuggingFace repo (default: %(default)s)")
    p.add_argument("--file", default=DEFAULT_FILE, help="Filename within the repo (default: %(default)s)")
    return p.parse_args(argv)


def main() -> int:
    args = parse_args()
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    target = MODELS_DIR / args.file
    if target.exists():
        size_mb = target.stat().st_size / (1024 * 1024)
        print(f"Already present: {target} ({size_mb:.1f} MB) — skipping download.")
        print(f'Set in .env:  PRAXIS_SLM_MODEL_PATH={target.relative_to(ROOT).as_posix()}')
        return 0

    if shutil.which("huggingface-cli") is None:
        print("huggingface-cli not on PATH. Install it once:\n    pip install huggingface_hub[cli]")
        return 2

    cmd = [
        "huggingface-cli",
        "download",
        args.repo,
        args.file,
        "--local-dir",
        str(MODELS_DIR),
        "--local-dir-use-symlinks",
        "False",
    ]
    print("Running:", " ".join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0:
        print(f"\nDownload failed (exit {rc}).")
        return rc

    print(f"\nDownloaded {target}")
    print(f'Set in .env:  PRAXIS_SLM_MODEL_PATH={target.relative_to(ROOT).as_posix()}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
