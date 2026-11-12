#!/usr/bin/env python3
"""Print or verify the provenance of a local GGUF.

Reads the model's own metadata (no network) and compares it with the record in
``config/models.json``. Optionally verifies the recorded Hugging Face revision
still resolves, which needs network access.

Examples:

    python3 scripts/check_models.py --list
    python3 scripts/check_models.py --model mtp_qwen35 --gguf ~/models/...gguf
    python3 scripts/check_models.py --model mtp_qwen35 --gguf ... --online

Requires ``gguf`` on PYTHONPATH. Point it at llama.cpp's ``gguf-py``:

    PYTHONPATH=$HOME/llama.cpp/gguf-py python3 scripts/check_models.py ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def read_metadata(path: Path) -> dict[str, object]:
    try:
        from gguf import GGUFReader  # type: ignore
    except ImportError:
        raise SystemExit(
            "gguf module not found. Run with "
            "PYTHONPATH=<llama.cpp>/gguf-py"
        )
    reader = GGUFReader(str(path))
    keys = [
        "general.name",
        "general.quantized_by",
        "general.repo_url",
        "general.base_model.0.repo_url",
        "general.license",
        "general.license.name",
        "general.size_label",
        "general.file_type",
        "general.architecture",
    ]
    out: dict[str, object] = {}
    for key in keys:
        field = reader.fields.get(key)
        if field is not None:
            try:
                out[key] = field.contents()
            except Exception:
                pass
    for key in ("qwen35moe.nextn_predict_layers",):
        field = reader.fields.get(key)
        if field is not None:
            try:
                out[key] = field.contents()
            except Exception:
                pass
    return out


def check_revision(repo: str, revision: str) -> bool:
    url = f"https://huggingface.co/api/models/{repo}/revision/{revision}"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return response.status == 200
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/models.json")
    parser.add_argument("--list", action="store_true", help="list recorded models")
    parser.add_argument("--model", help="model key from config/models.json")
    parser.add_argument("--gguf", type=Path, help="local GGUF to inspect")
    parser.add_argument("--online", action="store_true", help="verify the HF revision")
    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    models = config["models"]

    if args.list or not args.model:
        width = max(len(entry["file"]) for entry in models.values()) + 2
        print(f"{'key':18}{'file':<{width}}{'repo'}")
        for key, entry in models.items():
            print(f"{key:18}{entry['file']:<{width}}{entry.get('hf_repo','?')}")
        return 0

    entry = models.get(args.model)
    if not entry:
        raise SystemExit(f"unknown model key: {args.model}")

    print(f"recorded: {entry['file']}")
    print(f"  base model: {entry.get('base_model')}")
    print(f"  repo:       {entry.get('hf_repo')}")
    print(f"  revision:   {entry.get('hf_revision')}")
    print(f"  licence:    {entry.get('license')}")
    print(f"  sha256:     {entry.get('sha256')}")

    if args.gguf:
        if not args.gguf.exists():
            raise SystemExit(f"not found: {args.gguf}")
        meta = read_metadata(args.gguf)
        print("\nlocal GGUF metadata:")
        for key, value in meta.items():
            print(f"  {key} = {value}")
        actual = sha256(args.gguf)
        expected = entry.get("sha256")
        print(f"\n  sha256 = {actual}")
        if expected:
            print(f"  match  = {actual == expected}")
        if "general.base_model.0.repo_url" in meta:
            base = str(meta["general.base_model.0.repo_url"])
            print(f"  base matches record: {base.endswith(str(entry.get('base_model')))}")

    if args.online:
        repo = entry.get("hf_repo")
        revision = entry.get("hf_revision")
        if not repo or not revision:
            print("\nno recorded repo/revision to verify")
        else:
            ok = check_revision(repo, revision)
            print(f"\nrevision {revision[:12]} in {repo}: {'OK' if ok else 'NOT FOUND'}")
            return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
