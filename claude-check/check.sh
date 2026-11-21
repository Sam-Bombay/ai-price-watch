#!/usr/bin/env bash
# claude-check.sh — evidence collector for the 29-30 Oct 2026 compromise of
# Anthropic.claude-code 2.1.313 (Open VSX / VS Code Marketplace / Cursor Marketplace).
#
# Read-only. Changes nothing. Writes a dated evidence report you can hand to an
# insurer, a client, or a board, and exits 2 if anything is found.
#
# Checks are derived from the two published advisories:
#   Cursor security notice, 29 Oct 2026 (IOCs, hashes, remediation)
#   Phorion advisory, 30 Oct 2026 (macOS/Linux/Windows artifacts, persistence)
#
# Usage:  bash claude-check.sh            # check the user running it
#         bash claude-check.sh /Users/a /Users/b   # fleet mode, needs read access
#
# Official cleaner (not included here, use theirs): Cursor's remediate-macos.sh

set -u
FOUND=0
REPORT=""
TS=$(date -u "+%Y-%m-%dT%H:%M:%SZ")
OUT="claude-check-$(hostname -s)-$(date +%Y%m%d-%H%M%S).txt"

say() { REPORT="${REPORT}$1
"; }
hit() { FOUND=$((FOUND+1)); say "  [HIT]     $1"; }
ok()  { say "  [clear]   $1"; }
unk() { say "  [unknown] $1"; }

say "CLAUDE-CODE 2.1.313 COMPROMISE — HOST EVIDENCE REPORT"
say "host: $(hostname)   os: $(uname -s) $(uname -r) $(uname -m)   utc: $TS"
say "checker: claude-check.sh (read-only, no upload, no telemetry)"
say "sources: cursor.com/blog/claude-code-extension-security-notice (29 Oct 2026)"
say "         phorion.io/blog/offical-claude-code-vsx-compromise (30 Oct 2026)"
say ""

HOMES=("$@")
[ ${#HOMES[@]} -eq 0 ] && HOMES=("$HOME")

for H in "${HOMES[@]}"; do
  H="${H%/}"
  say "== home: $H"
  [ -r "$H" ] || { unk "$H not readable (re-run as that user or with sudo)"; continue; }

  # 1. the extension itself, every editor that carries a marketplace copy
  EXT_FOUND=0
  for IDE in .vscode .cursor .vscode-insiders .windsurf .positron .trae .kiro .void; do
    for D in "$H/$IDE/extensions" "$H/.vscode-server/extensions" "$H/.cursor-server/extensions"; do
      [ -d "$D" ] || continue
      for E in "$D"/anthropic.claude-code-2.1.313*; do
        [ -e "$E" ] || continue
        EXT_FOUND=1
        hit "malicious extension present: $E"
        if [ -f "$E/extension.js" ]; then
          SUM=$(shasum -a 256 "$E/extension.js" 2>/dev/null | cut -d' ' -f1)
          if [ "$SUM" = "ecb58cb29078d9646ad1dcdbe51526f2d9cfea06be5fb2ab183e8ecc3ab6bf15" ]; then
            hit "  extension.js matches published backdoored SHA-256"
          fi
          if grep -q "134.209.82.225" "$E/extension.js" 2>/dev/null; then
            hit "  extension.js contains attacker IP 134.209.82.225"
          fi
          if grep -q "svc-telemetry" "$E/extension.js" 2>/dev/null; then
            hit "  extension.js contains svc-telemetry strings"
          fi
        fi
      done
      # any other version still installed tells us the auto-update did not strip it
      for E in "$D"/anthropic.claude-code-2.1.31*; do
        case "$E" in *2.1.313*) continue;; esac
        [ -e "$E" ] || continue
        say "  [note]    other version installed: $(basename "$E")"
      done
    done
  done
  [ $EXT_FOUND -eq 0 ] && ok "no anthropic.claude-code-2.1.313 directory in any editor extensions folder"

  # 2. planted SSH key — the one definitive marker of execution
  AK="$H/.ssh/authorized_keys"
  if [ -f "$AK" ]; then
    if grep -q "svc-telemetry" "$AK" 2>/dev/null; then
      hit "$AK contains comment svc-telemetry (KEY PLANTED)"
    elif grep -q "AAAAC3NzaC1lZDI1NTE5AAAAIDdvylCEJ/k2TpezcTfedrkHyFSK9IZ3vmP6vhY4Ss0P" "$AK" 2>/dev/null; then
      hit "$AK contains the published attacker key blob"
    else
      ok "no svc-telemetry key in $AK ($(wc -l < "$AK" | tr -d ' ') keys total)"
    fi
    # fingerprint cross-check, comment could have been edited after the fact
    if command -v ssh-keygen >/dev/null 2>&1; then
      if ssh-keygen -lf "$AK" 2>/dev/null | grep -q "0Z6R+DF64Do2nwQic8a7kkfDLNNk4IiK+2U2Rci4htk"; then
        hit "key fingerprint SHA256:0Z6R+DF6... present in $AK"
      fi
      if ssh-keygen -lf "$AK" 2>/dev/null | grep -q "KOAU57+ZG6u3MG4WwzPzPX2O5YEe9qdOC1Bl+6MVyDQ"; then
        hit "tunnel key fingerprint SHA256:KOAU57+Z... present in $AK"
      fi
    fi
  else
    ok "no $AK (key could not have been planted there)"
  fi

  # macOS also has a system-level authorized_keys some admins use
  [ -f /Library/SSH/administrators_authorized_keys ] && \
    grep -q "svc-telemetry" /Library/SSH/administrators_authorized_keys 2>/dev/null && \
    hit "/Library/SSH/administrators_authorized_keys contains svc-telemetry"

  # 3. tunnel key left in temp dirs
  TK=0
  for T in "${TMPDIR:-/nonexistent}" /tmp /var/tmp; do
    [ -d "$T" ] || continue
    for F in "$T"/.stk_*; do
      [ -e "$F" ] || continue
      TK=1; hit "tunnel key file present: $F"
    done
  done
  [ $TK -eq 0 ] && ok "no .stk_* tunnel key in TMPDIR /tmp /var/tmp"

  # 4. persistence
  if [ -f "$H/.config/.smt" ] || [ -f "$H/.config/.smtk" ]; then
    hit "persistence script present: $H/.config/.smt / .smtk"
    [ -f "$H/.config/.smt" ] && say "          first line: $(head -1 "$H/.config/.smt" 2>/dev/null)"
  else
    ok "no ~/.config/.smt or ~/.config/.smtk"
  fi
  PL="$H/Library/LaunchAgents/com.apple.sysmond.plist"
  if [ -f "$PL" ]; then
    hit "LaunchAgent present: $PL"
    grep -q "/.config/.smt" "$PL" 2>/dev/null && hit "  LaunchAgent executes ~/.config/.smt"
  else
    ok "no com.apple.sysmond LaunchAgent"
  fi
  if [ "$(uname -s)" = "Linux" ] && command -v crontab >/dev/null 2>&1; then
    crontab -l 2>/dev/null | grep -q "@reboot.*\.smt" && hit "crontab @reboot entry runs .smt"
  fi
  [ -f "$H/.config/smt.cmd" ] && hit "Windows-style persistence present: $H/.config/smt.cmd"

  # 5. is a tunnel actually running right now
  if ps ax -o pid=,command= 2>/dev/null | grep -E "stk_|autossh|:0:localhost:22" | grep -v grep >/dev/null; then
    hit "live tunnel process found:"
    ps ax -o pid=,command= | grep -E "stk_|autossh|:0:localhost:22" | grep -v grep | sed 's/^/            /' | while read -r L; do say "$L"; done
  else
    ok "no reverse-SSH tunnel process running now"
  fi
done

# 6. network, once per host
say ""
say "== network"
if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP 2>/dev/null | grep -q "134.209.82.225"; then
  hit "open socket to 134.209.82.225 (see: lsof -nP -iTCP | grep 134.209.82.225)"
else
  ok "no current socket to 134.209.82.225"
fi
say "  [note]    the attacker server was taken offline 29-30 Oct, so a clean socket check does NOT clear the host"

# 7. sshd state — relevant because the backdoor only works if remote login is on
say ""
say "== ssh daemon"
if command -v systemsetup >/dev/null 2>&1; then
  RL=$(systemsetup -getremotelogin 2>&1)
  case "$RL" in
    *On*) say "  [note]    Remote Login is ON: $RL — the planted key WOULD work, do not wait" ;;
    *Off*) ok "Remote Login is Off ($RL)" ;;
    *) unk "cannot read Remote Login without admin: $RL" ;;
  esac
else
  if command -v systemctl >/dev/null 2>&1; then
    S=$(systemctl is-active ssh sshd 2>/dev/null | tr '\n' ' ')
    say "  [note]    ssh/sshd state: ${S:-unknown}"
  fi
fi

say ""
if [ $FOUND -gt 0 ]; then
  say "RESULT: $FOUND indicator(s) FOUND on $(hostname). Treat as compromised."
  say "Next: pull the box off the network, snapshot it, then run Cursor's official"
  say "remediate-macos.sh, then rotate every credential and token reachable from it."
  say "Persistence survives uninstalling the extension, and the fixed 2.1.314 does"
  say "NOT remove what 2.1.313 left behind (Beaumont, 30 Oct 2026)."
else
  say "RESULT: no indicators found on $(hostname) by this checker."
  say "This is an absence of evidence, not a clearance: it cannot see a host that was"
  say "rebuilt, and it cannot see other machines on the network."
fi
say ""
say "report written by claude-check.sh — read-only, nothing sent anywhere"

printf '%s' "$REPORT" | tee "$OUT"
echo
echo "saved: $(pwd)/$OUT"
[ $FOUND -gt 0 ] && exit 2
exit 0
