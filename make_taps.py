#!/usr/bin/env python3
"""Turn the approved outreach drafts into one-tap wa.me links.

Why: the drafts have been sitting unsent for days because sending means finding the
thread, scrolling, and pasting long copy on a phone. A prefilled wa.me link removes
every step except the tap. Text is the approved copy from OUTREACH.md, verbatim --
this script only encodes it, it does not rewrite it.

Writes: /Users/sambombay/money-ideas/taps/<date>.html  (tap on the phone)
Prints the links so they can go in the Telegram brief.
"""
import datetime
import os
import urllib.parse

OUT = "/Users/sambombay/money-ideas/taps"

# Numbers read from ChatStorage (ZWACHATSESSION.ZCONTACTJID), not guessed.
DRAFTS = [
    ("Omar — RabbitWash", "13239610535", "direct", """Omar, quick one on RabbitWash: the site had a Vercel login wall in front of it, which is why every link I sent you bounced to a sign-in page. Fixed this morning.

Site: https://rw-db79cd21.vercel.app
Owner/admin: https://rw-db79cd21.vercel.app/rw-admin/login

Hosting is $50/month - server, domain, monitoring, and me fixing anything that breaks. The app, Rabbit portal and admin work past what you have seen is $2,500 as a block.

Try it on your phone and tell me what is still broken."""),
    # The group id (120363429443081904@g.us) is NOT a phone number and wa.me cannot
    # open it -- the direct number above is the only reliable tap for Omar.
    ("Anil Relwani", "971556363050", "direct", """A: saw Atiq's new place. Before he signs with anyone - we do the whole launch in one go, site, menu, booking, the photos, and the WhatsApp line people actually use to book. If you want I'll send one page with the number on it. No deck, no meeting."""),
    ("Usamah Aussie Qureshi", "819056770773", "direct", """Heard your question about the AI coding - short answer is I've stopped writing most of it by hand, so the things that used to be six weeks are a week. If there's something you keep meaning to build, tell me what it is and I'll tell you straight whether it's a week or a waste of money. First scope's free either way."""),
]


def link(number, text, kind):
    q = urllib.parse.quote(text, safe="")
    if kind == "group":
        return f"https://wa.me/{number}?text={q}"
    return f"https://wa.me/{number}?text={q}"


def main():
    today = datetime.date.today().isoformat()
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for name, num, kind, text in DRAFTS:
        u = link(num, text, kind)
        rows.append((name, u, len(text)))

    html = ["<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>",
            "<title>One-tap sends</title>",
            "<style>body{font:17px/1.5 -apple-system,sans-serif;margin:0;padding:24px 18px;background:#fff}"
            "a.b{display:block;padding:18px;margin:0 0 14px;border:1px solid #ddd;border-radius:12px;"
            "text-decoration:none;color:#0a6c4f;font-weight:600}"
            "p{color:#666;font-size:14px}</style>",
            "<h1 style='font-size:22px'>One-tap sends</h1>",
            "<p>Each opens WhatsApp with the approved text already in the box. Nothing sends until you hit send.</p>"]
    for name, u, n in rows:
        html.append(f"<a class='b' href=\"{u}\">{name}<br><span style='font-weight:400;font-size:13px;color:#888'>{n} chars, prefilled</span></a>")
    html.append("</body>")
    p = os.path.join(OUT, f"{today}.html")
    open(p, "w").write("\n".join(html))

    print(f"wrote {p}\n")
    for name, u, n in rows:
        print(f"{name}\t{n} chars")
        print(u)
        print()


if __name__ == "__main__":
    main()
