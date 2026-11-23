#!/usr/bin/env python3
"""
openssl-check — read-only CVE-2026-121481 exposure read for one host.

What it does (no writes outside the report file, no network):
  1. reports the default OpenSSL/LibreSSL version the host actually resolves
  2. reports every libssl/libcrypto it can find, with version strings
  3. scans given source directories for EVP_EncodeBlock / EVP_DecodeBlock call
     sites and flags the ones whose length argument is not a literal, i.e. the
     only way this overflow can be reached by real code
  4. writes a dated text report that cites the source records

Usage:
  python3 openssl_check.py                 # host only
  python3 openssl_check.py --code ~/src    # host + code scan

Exit codes: 0 = report written.
"""
import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import time

CVE = "CVE-2026-121481"
SOURCES = [
    ("NVD record, published 2026-11-18, CVSS 3.1 9.8, status Awaiting Analysis",
     "https://nvd.nist.gov/vuln/detail/CVE-2026-121481"),
    ("GitHub advisory GHSA-83xj-7xh4-4p7x", "https://github.com/advisories/GHSA-83xj-7xh4-4p7x"),
]
VENDOR_CAVEAT = ("The OpenSSL advisory text states: 'No path by which an attacker can trigger "
                 "this has been identified.' A 9.8 score and a demonstrated trigger are not the same fact.")

CALL_RE = re.compile(r"\bEVP_(?:En|De)codeBlock\s*\(")
SCAN_EXT = {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".m", ".mm", ".go", ".rs", ".py", ".php",
            ".rb", ".java", ".kt", ".cs", ".swift", ".js", ".ts"}


def run(cmd):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        return (p.stdout or "") + (p.stderr or "")
    except Exception as e:  # noqa: BLE001
        return "ERROR: %s" % e


def openssl_version():
    out = {}
    if shutil.which("openssl"):
        out["openssl version"] = run("openssl version -a")[:1200].strip()
    else:
        out["openssl version"] = "openssl binary not found on PATH"
    # macOS system libcrypto is LibreSSL and is NOT the OpenSSL codebase
    for pat in ("libssl", "libcrypto"):
        found = run("ls -1 /usr/lib/%s*.dylib /usr/lib/x86_64-linux-gnu/%s*.so* "
                    "/lib/x86_64-linux-gnu/%s*.so* /usr/local/lib/%s* 2>/dev/null" % (pat, pat, pat, pat))
        out["libs:" + pat] = "\n".join(sorted({l for l in found.splitlines() if l.strip()})) or "none found"
    return out


def code_scan(roots, max_hits=200):
    hits, scanned = [], 0
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(os.path.expanduser(root)):
            dirnames[:] = [d for d in dirnames if d not in
                           {".git", "node_modules", "vendor", "build", "dist", "Pods", "__pycache__"}]
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() not in SCAN_EXT:
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    if os.path.getsize(p) > 2_000_000:
                        continue
                    with open(p, "r", errors="ignore") as fh:
                        for i, line in enumerate(fh, 1):
                            scanned += 1
                            if CALL_RE.search(line):
                                arg = line.split("(", 1)[1].strip()
                                # the encoded length is the LAST argument of EVP_EncodeBlock(out, in, len)
                                body = arg.rsplit(")", 1)[0]
                                last = body.rsplit(",", 1)[-1].strip().strip("); ")
                                literal = bool(re.match(r'^[0-9]+\b|^sizeof\b|^strlen\s*\(', last))
                                hits.append({"file": p, "line": i, "literal_len": literal,
                                             "text": line.strip()[:160]})
                                if len(hits) >= max_hits:
                                    return hits, scanned
                except OSError:
                    continue
    return hits, scanned


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", action="append", default=[], help="source dir to scan (repeatable)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_path = a.out or os.path.join(os.getcwd(), "openssl-check-%s-%s.txt" % (platform.node(), stamp))

    lines = []
    add = lines.append
    add("openssl-check — %s exposure read" % CVE)
    add("host      : %s (%s %s)" % (platform.node(), platform.system(), platform.release()))
    add("generated : %s" % time.strftime("%Y-%m-%d %H:%M:%S %Z"))
    add("read-only : no network calls, no files modified, output is this report")
    add("")
    add("Sources")
    for label, url in SOURCES:
        add("  - %s\n    %s" % (label, url))
    add("")
    add("Vendor caveat (quote)")
    add("  " + VENDOR_CAVEAT)
    add("")
    add("1. TLS library this host resolves")
    for k, v in openssl_version().items():
        add("  [%s]" % k)
        for ln in v.splitlines()[:12]:
            add("      " + ln)
    add("")
    add("   Reading: the overflow lives in OpenSSL's EVP_EncodeBlock(). LibreSSL, which macOS")
    add("   ships at /usr/lib/libcrypto.dylib, is a different codebase and is not covered by")
    add("   this advisory. Only a linked OpenSSL 1.1.1 / 3.x / 4.x build is in scope.")
    add("")
    if a.code:
        hits, scanned = code_scan(a.code)
        add("2. Call sites for EVP_EncodeBlock / EVP_DecodeBlock in supplied source")
        add("   scanned %d lines in %s" % (scanned, ", ".join(a.code)))
        add("   hits: %d" % len(hits))
        if not hits:
            add("   no call sites found — this CVE has nothing to reach in this source")
        else:
            reach = [h for h in hits if not h["literal_len"]]
            add("   call sites whose output-length argument is not an obvious literal: %d" % len(reach))
            for h in hits[:40]:
                add("   %s%s:%d  %s" % ("[length not literal] " if not h["literal_len"] else "",
                                        h["file"], h["line"], h["text"]))
        add("")
    add("3. What the numbers mean")
    add("   A build that links OpenSSL and passes an attacker-influenced length near INT_MAX to")
    add("   EVP_EncodeBlock() is the only reachable shape. No such path is published today, and the")
    add("   fix is an open pull request (openssl/openssl#33652, opened 2026-11-10) with no release")
    add("   carrying it yet. That is the whole exposure story: a critical-scored bug with no patch")
    add("   and no known trigger.")
    add("")
    add("Report written: %s" % out_path)

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("\nREPORT=%s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
