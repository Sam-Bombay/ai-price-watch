#!/usr/bin/env python3
"""Generate feed.xml (RSS 2.0) from the dated briefs in index.html.

Runs after every price fetch, so the feed is always as fresh as the page.
Distribution asset: aggregators, chamber newsletters and blogs can subscribe to
the daily AI price moves without anyone doing the work each day.
"""
import html as htmllib
import os
import re
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://ai-price-watch-beta.vercel.app"

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def strip_tags(s):
    return htmllib.unescape(re.sub(r"<[^>]+>", "", s)).replace("\n", " ").strip()


def parse_briefs(src):
    """Return [(date, title, html_body)] newest first, as laid out in the page."""
    out = []
    for block in re.findall(r'<div class="brief">(.*?)</div>', src, re.S):
        m = re.search(r'<p class="brief-k">(.*?)</p>', block, re.S)
        if not m:
            continue
        k = strip_tags(m.group(1))
        dm = re.search(r"(\d{1,2})\s+([A-Z][a-z]{2})\s+(\d{4})", k)
        if not dm:
            continue
        day, mon, year = int(dm.group(1)), MONTHS.get(dm.group(2)), int(dm.group(3))
        if not mon:
            continue
        date = datetime.date(year, mon, day)
        title = re.sub(r"\s*[—–-]\s*\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4}\s*$", "", k).strip(" —-")
        body = re.sub(r'<p class="brief-k">.*?</p>', "", block, flags=re.S).strip()
        body = re.sub(r'href="#(\w+)"', r'href="%s/#\1"' % SITE, body)
        out.append((date, title, body))
    out.sort(key=lambda r: r[0], reverse=True)
    return out


def rfc822(d):
    return datetime.datetime(d.year, d.month, d.day, 7, 30,
                             tzinfo=datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")


def main():
    src = open(os.path.join(HERE, "index.html"), encoding="utf-8").read()
    briefs = parse_briefs(src)
    if not briefs:
        print("feed: no briefs found, feed not rewritten")
        return
    items = []
    for date, title, body in briefs:
        link = "%s/#brief-%s" % (SITE, date.isoformat())
        items.append(
            "    <item>\n"
            "      <title>%s</title>\n"
            "      <link>%s</link>\n"
            "      <guid isPermaLink=\"false\">ai-price-watch-%s</guid>\n"
            "      <pubDate>%s</pubDate>\n"
            "      <description><![CDATA[%s]]></description>\n"
            "    </item>" % (htmllib.escape(title), link, date.isoformat(), rfc822(date), body))
    newest = briefs[0][0]
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        "    <title>AI Price Watch — daily AI model price moves</title>\n"
        "    <link>%s</link>\n"
        "    <description>What every AI model costs per million tokens, and what moved today. "
        "Feeds an AI cost audit: I track the prices, you keep 70%% of what I cut.</description>\n"
        "    <language>en-us</language>\n"
        "    <lastBuildDate>%s</lastBuildDate>\n"
        "    <atom:link href=\"%s/feed.xml\" rel=\"self\" type=\"application/rss+xml\"/>\n"
        "%s\n"
        "  </channel>\n"
        "</rss>\n" % (SITE, rfc822(newest), SITE, "\n".join(items)))
    open(os.path.join(HERE, "feed.xml"), "w", encoding="utf-8").write(feed)
    print("feed: wrote %d briefs, newest %s" % (len(briefs), newest))


if __name__ == "__main__":
    main()