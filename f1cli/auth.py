"""
F1TV authentication — wraps FastF1's built-in browser auth flow.

FastF1 uses a browser-based login:
1. Opens a URL in your browser
2. You log in on formula1.com
3. Token is captured via localhost callback
4. Token is saved to ~/.local/share/fastf1/f1auth.json

"""

from __future__ import annotations


def ensure_auth():
    """
    Check if we have a valid auth token.
    If not, triggers the browser login flow.
    """
    from fastf1.internals.f1auth import get_auth_token
    token = get_auth_token()
    if token:
        print("  ● Authenticated with F1TV")
    else:
        print("  ● Authentication failed — live timing may not work")
    return token


def show_status():
    """Print current auth status."""
    try:
        from fastf1.internals.f1auth import print_auth_status
        print_auth_status()
    except Exception as e:
        print(f"  Not authenticated: {e}")


def logout():
    """Clear saved auth token."""
    try:
        from fastf1.internals.f1auth import clear_auth_token
        clear_auth_token()
        print("  Auth token cleared.")
    except Exception as e:
        print(f"  Could not clear token: {e}")
