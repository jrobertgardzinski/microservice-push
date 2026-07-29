"""Push-notification channel microservice — one of the paddock's notification channels (e-mail and
SMS are its siblings). Framework-free HTTP, the same uniform channel contract as the others.

    POST /send   {"to": "<device-token>", "subject": "title", "body": "..."}  -> 202 {"status":"SENT"}
    GET  /health                                                              -> 200 {"status":"UP"}

By default it STUB-sends: it validates the device token and message and logs — so the stack runs
with no FCM/APNs account. Point PUSH_PROVIDER at a real service (e.g. fcm) with credentials to send
for real; the wire contract the paddock speaks never changes. Here `to` is a device token, `subject`
is the notification title, `body` is its text.
"""

import hmac
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

SERVICE = "push"

def log(level, message):
    """The stack's shared log line (observability/README.md in the aggregator repo): ISO
    time, level, cid/trace placeholders (this stdlib stack sets neither), service, message."""
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")
    print(f"{stamp} {level:<5} [cid=-] [trace=-] {SERVICE} - {message}", flush=True)


PROVIDER = os.environ.get("PUSH_PROVIDER", "stub")
# The same guard the sibling mail service has had all along: only trusted callers may send. Without
# it this endpoint takes a message from anything that can reach the port — today the compose network
# (every container in the stack), and the README's own next step is "point PUSH_PROVIDER at a real gateway
# and give it credentials", at which point an unauthenticated endpoint becomes a paid-push pump
# and a phishing channel ("Your sign-in code is ..." from the portal's own number).
API_KEY = os.environ.get("PUSH_API_KEY")
# Fail-CLOSED once a provider is real. An absent key used to mean "let everyone in", which is the
# wrong default for the branch that matters: the stub is a toy, but a configured gateway sends
# paid messages on somebody's account. With a real provider and no key the service refuses to
# start, the way the mail service refuses to start without MAIL_API_KEY — a deployment that forgot
# the secret should not come up as an open relay.
if PROVIDER != "stub" and not API_KEY:
    raise SystemExit(
        f"PUSH_API_KEY is required when PUSH_PROVIDER is not 'stub': refusing to start an unauthenticated"
        f" gateway that sends for real")
# A request body this service has any business reading: every legitimate one is a short JSON object.
MAX_BODY_BYTES = 8192

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
        # metadata only: a notification's title and body are the user's own content, and these logs
        # go to Loki (see the sibling sms service, where the same line carried MFA codes)
        log("INFO", f"stub delivery to {to[:12]}... ({len(title)}+{len(text)} chars)")
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
        if API_KEY and not hmac.compare_digest(self.headers.get("X-Api-Key", ""), API_KEY):
            self._json(401, {"status": "UNAUTHORIZED"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._json(400, {"status": "BAD_REQUEST", "error": "invalid Content-Length"})
            return
        if length > MAX_BODY_BYTES:
            self._json(413, {"status": "REJECTED", "error": "body too large"})
            return
        try:
            payload = json.loads(self.rfile.read(max(0, length)) or b"{}")
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
        log("INFO", f"{self.command} {self.path}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8089"))
    log("INFO", f"push channel listening on {port} (provider={PROVIDER})")
    ThreadingHTTPServer(("", port), Handler).serve_forever()
