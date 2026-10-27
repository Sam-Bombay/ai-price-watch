#!/bin/bash
# Free, permanent mirror of AI Price Watch on GitHub Pages.
# Why: the vercel.app project is on a $20/mo plan whose card failed 24 Oct 2026
# ("Payment Failed And Shutdown Coming Soon"). The Pages mirror is $0 forever, so the
# funnel (clinic -> audit) survives even if Vercel suspends.
# Usage: ./publish_gh_pages.sh        (publishes the current local static tree)
set -uo pipefail
cd /Users/sambombay/money-ideas/tracker || exit 1

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# static assets only — no python, no caches, no git metadata
for f in index.html feed.xml; do [ -f "$f" ] && cp "$f" "$TMP/"; done
for d in data clinic receipts volatility local-stt embed workbench msp repricing; do
  [ -d "$d" ] && cp -R "$d" "$TMP/"
done
rm -rf "$TMP"/workbench/__pycache__ "$TMP"/workbench/*.py "$TMP"/workbench/*.csv
touch "$TMP/.nojekyll"

# GitHub Pages serves this repo from a subpath (/ai-price-watch/), so absolute links
# written for the vercel.app root would 404 here. Rewrite them in the mirror only.
BASE=/ai-price-watch
python3 - "$TMP" "$BASE" <<'PY'
import sys, os, re
root, base = sys.argv[1], sys.argv[2]
files = []
for d, _, fs in os.walk(root):
    for f in fs:
        if f.endswith('.html'): files.append(os.path.join(d, f))
for p in files:
    s = open(p, encoding='utf-8', errors='ignore').read()
    o = s
    s = s.replace('href="/"', 'href="%s/"' % base)
    s = re.sub(r'href="/(?!/|%s|ai-price-watch)' % base.strip('/'), 'href="%s/' % base, s)
    s = re.sub(r'src="/(?!/|%s|ai-price-watch)' % base.strip('/'), 'src="%s/' % base, s)
    s = re.sub(r'(fetch\(["\'])/(?!/|%s|ai-price-watch)' % base.strip('/'), r'\1%s/' % base, s)
    if s != o:
        open(p, 'w', encoding='utf-8').write(s)
print('rewrote', len(files), 'html files')
PY

cd "$TMP" || exit 1
git init -q -b gh-pages
git add -A
git -c user.email=sambombayoffice@gmail.com -c user.name="Sam Bombay" \
    commit -q -m "pages: $(date +%Y-%m-%d)"
git push -q --force "https://github.com/Sam-Bombay/ai-price-watch.git" gh-pages
RC=$?
if [ $RC -eq 0 ]; then echo "pushed gh-pages"; else echo "push FAILED"; fi
exit $RC
