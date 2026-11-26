#!/usr/bin/env python3
"""Read-only agent access inventory.

Answers one question a CTO cannot currently answer: which local AI agents and
coding tools hold credentials on this machine, where are those credentials
stored, who can read the file, and which MCP servers have been wired in.

It never prints, copies or transmits a secret value. It records the file path,
the file mode, the line number and the provider the key belongs to.

Usage:
  python3 agent_access_audit.py            # text report to stdout
  python3 agent_access_audit.py --json r.json
  python3 agent_access_audit.py --root /Users/someone
"""
import argparse
import json
import os
import re
import stat

HOME = os.path.expanduser("~")

# Directories that hold agent/tool state. Missing ones are simply skipped.
AGENT_DIRS = [
    ".hermes", ".openclaw", ".claude", ".codex", ".cursor", ".continue",
    ".aider", ".config/gh", ".aws", ".ssh", ".netrc", ".gemini",
    ".config/goose", ".config/opencode", ".windsurf", ".lmstudio",
]

# Provider key shapes. Named so the report is useful without the value.
SECRET_PATTERNS = [
    ("huggingface", re.compile(r"\bhf_[A-Za-z0-9]{20,}")),
    ("openai/anthropic", re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_\-]{20,}")),
    ("openrouter", re.compile(r"\bsk-or-v1-[A-Za-z0-9]{20,}")),
    ("fly.io", re.compile(r"\bfm2_[A-Za-z0-9_\-]{20,}")),
    ("github", re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("aws", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}")),
    ("slack", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}")),
    ("stripe", re.compile(r"\b(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{10,}")),
    ("shopify", re.compile(r"\bshpat_[0-9a-fA-F]{32}")),
    ("elevenlabs", re.compile(r"\bsk_[0-9a-f]{32,}")),
    ("telegram", re.compile(r"\b\d{8,10}:AA[0-9A-Za-z_\-]{30,}")),
    ("xai/groq/mistral", re.compile(r"\b(?:xai-|gsk_|ntn_)[0-9A-Za-z_\-]{20,}")),
]

SKIP_DIRS = {"node_modules", ".git", "__pycache__", "site-packages", "dist",
             "build", ".venv", "venv", "Cache", "cache", "Downloads", "caches",
             "sessions", "session", "logs", "history", "tmp", "temp", "backups",
             "Crashpad", "Code Cache", "GPUCache", "blob_storage"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".mp3",
            ".wav", ".pdf", ".zip", ".gz", ".tar", ".db", ".sqlite", ".sqlite3",
            ".wal", ".shm", ".whl", ".so", ".dylib", ".bin", ".ico"}
MAX_FILES = 3000
MAX_BYTES = 2 * 1024 * 1024
MAX_DEPTH = 6

MCP_FILES = [".claude.json", ".cursor/mcp.json", ".codex/config.toml",
             ".openclaw/openclaw.json", ".openclaw/config.json"]


def walk(root):
    base_depth = root.rstrip(os.sep).count(os.sep)
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        if dirpath.count(os.sep) - base_depth >= MAX_DEPTH:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if os.path.splitext(f)[1].lower() in SKIP_EXT:
                continue
            seen += 1
            if seen > MAX_FILES:
                return
            yield os.path.join(dirpath, f)


def file_secrets(path):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return []
    except OSError:
        return []
    try:
        with open(path, "r", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return []
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for provider, pat in SECRET_PATTERNS:
            if pat.search(line):
                hits.append({"provider": provider, "line": lineno})
    return hits


def mode_of(path):
    try:
        m = os.stat(path).st_mode
    except OSError:
        return "?"
    return oct(stat.S_IMODE(m))


def world_readable(path):
    try:
        return bool(os.stat(path).st_mode & stat.S_IROTH)
    except OSError:
        return False


def mcp_servers(home):
    found = {}
    for rel in MCP_FILES:
        p = os.path.join(home, rel)
        if not os.path.isfile(p):
            continue
        try:
            raw = open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        names = set(re.findall(r'"mcpServers"\s*:\s*\{([^}]*)\}', raw, re.S))
        servers = set()
        for block in names:
            servers.update(re.findall(r'"([A-Za-z0-9_.\- ]+)"\s*:\s*\{', block))
        if servers:
            found[rel] = sorted(servers)
    return found


def git_tracked(home, paths):
    """Which of the credential files sit inside a git work tree and are tracked."""
    tracked = []
    for p in paths:
        d = os.path.dirname(p)
        while d and d != "/":
            if os.path.isdir(os.path.join(d, ".git")):
                rel = os.path.relpath(p, d)
                gi = os.path.join(d, ".git", "index")
                try:
                    data = open(gi, "rb").read()
                    if rel.encode() in data:
                        tracked.append(p)
                except OSError:
                    pass
                break
            d = os.path.dirname(d)
    return tracked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=HOME)
    ap.add_argument("--json")
    args = ap.parse_args()
    home = os.path.abspath(os.path.expanduser(args.root))

    surfaces, findings = [], []
    for rel in AGENT_DIRS:
        p = os.path.join(home, rel)
        if not os.path.exists(p):
            continue
        if os.path.isfile(p):
            files = [p]
            name = rel
        else:
            files = list(walk(p))
            name = rel
        keyfiles = 0
        for f in files:
            hits = file_secrets(f)
            if not hits:
                continue
            keyfiles += 1
            findings.append({
                "surface": name,
                "path": f.replace(home, "~"),
                "mode": mode_of(f),
                "world_readable": world_readable(f),
                "providers": sorted({h["provider"] for h in hits}),
                "lines": len(hits),
            })
        surfaces.append({"surface": name, "path": rel, "files": len(files),
                         "credential_files": keyfiles})

    tracked = git_tracked(home, [os.path.join(home, f["path"][2:]) for f in findings])
    mcp = mcp_servers(home)

    report = {
        "root": home,
        "surfaces_found": len(surfaces),
        "surfaces": surfaces,
        "credential_files": len(findings),
        "secrets_by_provider": {},
        "world_readable": sum(1 for f in findings if f["world_readable"]),
        "git_tracked": [p.replace(home, "~") for p in tracked],
        "mcp_servers": mcp,
        "findings": findings,
    }
    providers = {}
    for f in findings:
        for p in f["providers"]:
            providers[p] = providers.get(p, 0) + 1
    report["secrets_by_provider"] = dict(sorted(providers.items(), key=lambda kv: -kv[1]))

    print("AGENT ACCESS REPORT")
    print("root: %s" % home)
    print("agent surfaces found: %d of %d known locations" % (len(surfaces), len(AGENT_DIRS)))
    print("files holding credentials: %d" % len(findings))
    print("of those, world-readable: %d" % report["world_readable"])
    print("of those, inside a git work tree and tracked: %d" % len(report["git_tracked"]))
    print("providers implicated: %s" % (", ".join(report["secrets_by_provider"]) or "none"))
    print()
    print("MCP servers wired in: %d config file(s)" % len(mcp))
    for f, servers in mcp.items():
        print("  %s: %s" % (f, ", ".join(servers)))
    print()
    for f in findings:
        flags = []
        if f["world_readable"]:
            flags.append("WORLD-READABLE")
        if f["path"] in [t.replace(home, "~") for t in report["git_tracked"]]:
            flags.append("GIT-TRACKED")
        print("%-28s %-46s mode %-5s %-2d key(s) %s %s" % (
            f["surface"], f["path"][:46], f["mode"], f["lines"],
            ",".join(f["providers"]), " ".join(flags)))
    print()
    print("No secret value was read into this report; only path, mode, provider and line count.")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print("json written: %s" % args.json)


if __name__ == "__main__":
    main()
