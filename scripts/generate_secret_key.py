#!/usr/bin/env python3
"""
Generate a secure secret key for Flask.
"""
import secrets
import sys

def main():
    """Generate and print a secret key."""
    key = secrets.token_hex(32)
    print("Generated Flask Secret Key:")
    print(key)
    print("\nAdd this to your .env file:")
    print(f"FLASK_SECRET_KEY={key}")
    return 0

if __name__ == '__main__':
    sys.exit(main())

