"""Issues one short-lived session token for local verification.

Run inside the api container only for checking an authenticated endpoint by
hand; the token is printed so it can be used with curl.
"""

import hashlib
import secrets

from app import connect

token = secrets.token_urlsafe(32)
with connect() as db:
    db.execute(
        "INSERT INTO sessions (token_hash, expires) VALUES (%s, now() + interval '30 minutes')",
        (hashlib.sha256(token.encode()).hexdigest(),),
    )
print(token)
