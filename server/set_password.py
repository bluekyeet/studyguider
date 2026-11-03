"""Create the first administrator, or reset any account's password, from the command line.

  docker compose exec api python set_password.py            # prompts for a username and password

If the username does not exist it is created as an administrator (use this on a brand new installation).
"""
import getpass
import sys

import userspace
from accounts import MIN_PASSWORD, clean_username, create_account_tables
from app import connect_account, hasher, provision_account

username = clean_username(sys.argv[1] if len(sys.argv) > 1 else input("Username: "))
password = getpass.getpass("New password: ")
if len(password) < MIN_PASSWORD or password != getpass.getpass("Confirm password: "):
    raise SystemExit(f"Password must be at least {MIN_PASSWORD} characters and both entries must match.")
with connect_account() as db:
    create_account_tables(db)
    row = db.execute("SELECT id FROM users WHERE lower(username) = lower(%s) FOR UPDATE", (username,)).fetchone()
    if row:
        user_id = row[0]
        db.execute("UPDATE users SET password_hash = %s, failed_logins = 0, locked_until = NULL WHERE id = %s", (hasher.hash(password), user_id))
        db.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
        print(f"Password set for {username}; their sessions were signed out.")
    else:
        user_id = db.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, true) RETURNING id", (username, hasher.hash(password))).fetchone()[0]
        print(f"Administrator {username} created.")
provision_account(user_id)
