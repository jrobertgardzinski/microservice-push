"""The push channel validates the device token and message; the stub delivers deterministically."""

import unittest

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


if __name__ == "__main__":
    unittest.main()
