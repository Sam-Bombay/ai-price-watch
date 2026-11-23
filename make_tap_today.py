#!/usr/bin/env python3
"""Build a one-tap message draft. Opening WhatsApp is not sending it."""
import urllib.parse, pathlib
INVOICE = ("https://invoice.stripe.com/i/acct_1TAQQZAizwophOvP/"
           "live_YWNjdF8xVEFRUVpBaXp3b3BoT3ZQLF9WY2JpM2FlYnd5UDZoMEplTHdQRzRqSVRnUjBZeUI0LDE4NTEyNDkwMw0200UL1j4eAm?s=ap")
BODY = f"""Omar, the trash-bin form logged a two-bin request from Burbank yesterday. That's the site doing its job. The notification went to support@rabbitwash.com, so it reached your support channel. I also sent the $2,550 invoice link by email. If the build looks right, can you clear it when you get a minute?\n\n{INVOICE}"""
LINK = "https://wa.me/13239610535?text=" + urllib.parse.quote(BODY, safe='')
html = f"""<meta name=viewport content='width=device-width,initial-scale=1'><body style='font:17px -apple-system;padding:24px;max-width:640px'><h3>RabbitWash — draft, 16 Nov</h3><p><a href=\"{LINK}\" style='font-size:20px'>Open Omar's WhatsApp thread with message</a></p><p style='color:#666;font-size:13px'>Opening the link is not sending. Press send in WhatsApp to deliver.</p><hr><pre style='white-space:pre-wrap;font:15px -apple-system'>{BODY}</pre></body>"""
out=pathlib.Path('/Users/sambombay/money-ideas/taps/2026-11-16.html')
out.write_text(html)
print('wrote',out,'bytes',len(html))
print('message states correct support destination:', 'went to support@rabbitwash.com' in BODY)
print('wa.me is only a draft link; no message sent')
