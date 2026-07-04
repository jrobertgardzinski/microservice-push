"""Push-notification channel microservice — one of the paddock's notification channels (e-mail and
SMS are its siblings). Framework-free HTTP, the same uniform channel contract as the others.

    POST /send   {"to": "<device-token>", "subject": "title", "body": "..."}  -> 202 {"status":"SENT"}
    GET  /health                                                              -> 200 {"status":"UP"}

By default it STUB-sends: it validates the device token and message and logs — so the stack runs
with no FCM/APNs account. Point PUSH_PROVIDER at a real service (e.g. fcm) with credentials to send
for real; the wire contract the paddock speaks never changes. Here `to` is a device token, `subject`
is the notification title, `body` is its text.
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PROVIDER = os.environ.get("PUSH_PROVIDER", "stub")
# device tokens are opaque but bounded: base64url-ish, a sane length window
TOKEN = re.compile(r"^[A-Za-z0-9_\-:.]{16,4096}$")
MAX_TITLE = 120
MAX_BODY = 2000


def send(to, subject, body):
    """Deliver one push (or refuse it). Returns the provider's message id. Raises ValueError on a
    bad request. The stub provider logs; a real provider would call FCM/APNs here."""
    if not to or not TOKEN.match(to):
        raise ValueError("not a valid device token")
    title = (subject or "").strip()
    text = (body or "").strip()
    if not title and not text:
        raise ValueError("empty notification")
    if len(title) > MAX_TITLE or len(text) > MAX_BODY:
        raise ValueError("notification too long")
    if PROVIDER == "stub":
        print(f"push-stub: to {to[:12]}...: {title!r} / {text[:40]!r}", flush=True)
        return "stub-" + str(abs(hash((to, title, text))) % 10_000_000)
    raise ValueError(f"unknown PUSH_PROVIDER: {PROVIDER}")   # real providers plug in here


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if urlparse(self.path).path == "/health":
            self._json(200, {"status": "UP", "provider": PROVIDER})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/send":
            self._json(404, {"error": "not found"})
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            self._json(400, {"status": "BAD_REQUEST", "error": "invalid JSON"})
            return
        try:
            message_id = send(payload.get("to"), payload.get("subject"), payload.get("body"))
        except ValueError as bad:
            self._json(400, {"status": "REJECTED", "error": str(bad)})
            return
        self._json(202, {"status": "SENT", "channel": "push", "id": message_id})

    def _json(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f"push: {self.command} {self.path}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8089"))
    print(f"push channel listening on {port} (provider={PROVIDER})")
    ThreadingHTTPServer(("", port), Handler).serve_forever()
