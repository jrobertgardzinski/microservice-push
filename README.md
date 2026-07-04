# microservice-push

A push-notification channel for the paddock — a sibling of `microservice-email` and
`microservice-sms`. Framework-free Python (stdlib only), the uniform channel contract:

```
POST /send   {"to": "<device-token>", "subject": "title", "body": "..."}  -> 202 {"status":"SENT"}
GET  /health                                                              -> 200 {"status":"UP"}
```

By default it **stub-sends**: validates the device token and message, logs, returns a deterministic
id — so the whole stack runs with no FCM/APNs account. Set `PUSH_PROVIDER` and credentials to send
for real; the wire contract never changes. `to` is the device token, `subject` the title, `body`
the text.

```bash
python3 server.py                 # :8089, stub provider
python3 -m unittest test_server
```
