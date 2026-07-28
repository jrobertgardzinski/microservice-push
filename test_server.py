"""The push channel validates the device token and message; the stub delivers deterministically."""

import contextlib
import io
import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import server
from server import send


class PushTest(unittest.TestCase):

    def test_a_valid_push_is_sent(self):
        mid = send("d1e2v3i4c5e6token7890", "Race Friday", "Lights out 20:00")
        self.assertTrue(mid.startswith("stub-"))

    def test_deterministic_stub_id(self):
        tok = "d1e2v3i4c5e6token7890"
        self.assertEqual(send(tok, "a", "b"), send(tok, "a", "b"))

    def test_a_bad_token_is_refused(self):
        for bad in (None, "", "short", "has spaces in it and stuff"):
            with self.assertRaises(ValueError):
                send(bad, "s", "b")

    def test_an_empty_notification_is_refused(self):
        with self.assertRaises(ValueError):
            send("d1e2v3i4c5e6token7890", "", "")


class BoundaryTest(unittest.TestCase):
    """The HTTP edge, mirroring the sibling sms service: who may send, and what the log may say."""

    @classmethod
    def setUpClass(cls):
        server.API_KEY = "test-key"                       # as compose now configures it
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        server.API_KEY = None
        cls.server.shutdown()
        cls.server.server_close()

    def post(self, payload, headers=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request("POST", "/send", json.dumps(payload),
                           {"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse()
        response.read()
        connection.close()
        return response

    def test_a_send_without_the_api_key_is_refused(self):
        message = {"to": "d1e2v3i4c5e6token7890", "title": "Race Friday", "body": "Lights out 20:00"}

        self.assertEqual(401, self.post(message).status)
        self.assertEqual(202, self.post(message, {"X-Api-Key": "test-key"}).status)

    def test_the_log_never_carries_the_notification_text(self):
        # a title and body are the user's own content, and this stdout goes to Loki
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            send("d1e2v3i4c5e6token7890", "Race Friday", "Lights out 20:00")
        written = captured.getvalue()

        self.assertNotIn("Lights out", written)
        self.assertNotIn("Race Friday", written)


if __name__ == "__main__":
    unittest.main()
