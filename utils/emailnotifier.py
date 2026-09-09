import smtplib
import time
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.settings import ENABLE_EMAIL, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_RECIPIENT

# File to persist the tracker (optional, but recommended)
TRACKER_FILE = "email_tracker.json"

# In‑memory dictionary: {symbol: last_timestamp}
_email_tracker = {}

def _load_tracker():
    """Load tracker from file if it exists."""
    global _email_tracker
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r') as f:
                _email_tracker = json.load(f)
        except Exception as e:
            print(f"[EMAIL TRACKER] Failed to load: {e}")

def _save_tracker():
    """Save tracker to file."""
    try:
        with open(TRACKER_FILE, 'w') as f:
            json.dump(_email_tracker, f)
    except Exception as e:
        print(f"[EMAIL TRACKER] Failed to save: {e}")

def can_send_email(symbol, cooldown_seconds):
    """
    Check if an email for `symbol` can be sent.
    Returns True if no email was sent for this symbol in the last `cooldown_seconds`.
    """
    if symbol is None:
        return True  # No symbol -> always allow (or handle differently)
    last = _email_tracker.get(symbol)
    if last is None:
        return True
    return (time.time() - last) >= cooldown_seconds

def mark_email_sent(symbol):
    """Record that an email has just been sent for `symbol`."""
    if symbol is not None:
        _email_tracker[symbol] = time.time()
        _save_tracker()   # Save after each update

def send_email(subject, body, symbol=None, cooldown_seconds=None):
    """
    Send an email, optionally with per‑symbol rate limiting.
    If `symbol` and `cooldown_seconds` are given, the email is sent only if
    the last email for that symbol was sent more than `cooldown_seconds` ago.
    """
    if not ENABLE_EMAIL:
        return

    # Rate limit check
    if symbol is not None and cooldown_seconds is not None:
        if not can_send_email(symbol, cooldown_seconds):
            print(f"[EMAIL] Skipped for {symbol} – cooldown active")
            return

    # Compose and send the email
    msg = MIMEMultipart()
    msg['From'] = SMTP_USERNAME
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("[EMAIL] Sent.")

        # Record the send time if a symbol was provided
        if symbol is not None:
            mark_email_sent(symbol)
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")

# Load existing tracker on module import
_load_tracker()