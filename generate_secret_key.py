#!/usr/bin/env python3
"""
Generate a secure random secret key for Flask application.
Run: python generate_secret_key.py
"""
import secrets

if __name__ == '__main__':
    secret_key = secrets.token_hex(32)
    print("=" * 60)
    print("FLASK SECRET KEY GENERATOR")
    print("=" * 60)
    print("\nYour new secret key:")
    print(f"\n{secret_key}\n")
    print("Copy this key to your .env file:")
    print(f"\nFLASK_SECRET_KEY={secret_key}\n")
    print("=" * 60)
