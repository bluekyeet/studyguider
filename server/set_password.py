import getpass

from app import connect, hasher

password = getpass.getpass("New password: ")
if len(password) < 12 or password != getpass.getpass("Confirm password: "):
    raise SystemExit("Password must be at least 12 characters and both entries must match.")
with connect() as db:
    db.execute("INSERT INTO settings VALUES ('password_hash', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (hasher.hash(password),))
    db.execute("DELETE FROM sessions")
    db.execute("DELETE FROM settings WHERE key IN ('login_failures', 'locked_until')")
print("Password set; existing sessions revoked.")
