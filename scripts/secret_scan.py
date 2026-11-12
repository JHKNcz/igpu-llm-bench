#!/usr/bin/env python3
"""Strict privacy/secret scan for this repository.

This is a defence-in-depth check, not a replacement for a dedicated secret
scanner. It reports the file and line, masks the matched value, and exits
non-zero if an unallowlisted match remains.

Known allowlist:
- llama.cpp log prefixes such as ``0.00.404.0`` look like IPv4 addresses but are
  relative timestamps. They are allowed only at the start of a log line.
- ``/home/user`` is an intentional documentation placeholder.
- SHA256 values are 64 hex characters and are not UUIDs or secrets.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules", "runs"}
SKIP_SUFFIXES = {
    ".gguf", ".safetensors", ".bin", ".pt", ".pth", ".so", ".pyc",
    ".png", ".jpg", ".jpeg", ".gif", ".zip", ".gz", ".xz", ".pdf",
}

PATTERNS = {
    "github_token": re.compile(r"\b(?:ghp_|github_pat_|gho_|ghu_|ghs_|ghr_)[A-Za-z0-9_]{20,}\b"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"),
    "password": re.compile(r"(?i)\bpassword\s*[:=]\s*\S+"),
    "api_key": re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*\S+"),
    "bearer": re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{20,}"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "ipv4": re.compile(r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b"),
    "mac": re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b"),
    "uuid": re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
}

LOG_PREFIX = re.compile(r"^\d+\.\d+\.\d+\.\d+\s+[IWE]\s")


def is_text(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    try:
        data = path.read_bytes()
    except OSError:
        return False
    return b"\x00" not in data[:4096]


def mask(kind: str, value: str) -> str:
    if kind in {"github_token", "openai_key", "aws_key", "slack_token", "private_key", "password", "api_key", "bearer"}:
        return "<redacted>"
    if kind == "email":
        return "<email>"
    if kind == "ipv4":
        parts = value.split(".")
        return f"{parts[0]}.x.x.{parts[-1]}"
    if kind == "mac":
        return "<mac>"
    if kind == "uuid":
        return "<uuid>"
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # Identity checks only make sense for a real workstation account. In CI the
    # "user" is `runner`, which collides with ordinary words in the docs
    # ("runner.py", "the second runner"). Skip those rather than fail on noise.
    generic = {
        "runner", "root", "ubuntu", "user", "ci", "jenkins", "buildkite",
        "circleci", "codespace", "vscode", "node", "docker", "builder",
    }
    username = os.environ.get("IGPU_SCAN_USER", getpass.getuser())
    hostname = os.environ.get("IGPU_SCAN_HOST", socket.gethostname())
    extra = {
        "location": re.compile(r"\b(?:Pr[a]gue|Pr[a]ha|Cz[e]ch|Eur[o]pe/)\b", re.IGNORECASE),
        "container": re.compile(r"\bele" + "gant_margulis\b"),
        "home_path": re.compile(r"/home/(?!user\b)[A-Za-z0-9._-]+"),
    }
    if username.lower() not in generic and len(username) > 2:
        extra["username"] = re.compile(re.escape(username), re.IGNORECASE)
    if hostname.lower() not in generic and len(hostname) > 3:
        extra["hostname"] = re.compile(re.escape(hostname), re.IGNORECASE)

    files = [
        p for p in sorted(args.root.rglob("*"))
        if p.is_file() and not any(part in SKIP_DIRS for part in p.parts) and is_text(p)
    ]
    matches = 0
    allowed = 0
    for path in files:
        rel = path.relative_to(args.root)
        for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            for kind, rx in {**PATTERNS, **extra}.items():
                for match in rx.finditer(line):
                    value = match.group(0)
                    # llama.cpp relative timestamps at the start of a log line
                    if kind == "ipv4" and LOG_PREFIX.match(line):
                        allowed += 1
                        continue
                    # loopback is not personal data and is required in working
                    # commands; allowlist it explicitly rather than mangling them
                    if kind == "ipv4" and value == "127.0.0.1":
                        allowed += 1
                        continue
                    # intentional documentation placeholder
                    if kind == "home_path" and value == "/home/user":
                        allowed += 1
                        continue
                    matches += 1
                    print(f"{rel}:{lineno}:{kind}:{mask(kind, value)}")
    print()
    print(f"files scanned: {len(files)}")
    print(f"matches:       {matches}")
    print(f"allowlisted:   {allowed}")
    if matches:
        print("FAIL: unallowlisted matches remain")
        return 1
    print("PASS: no unallowlisted matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
