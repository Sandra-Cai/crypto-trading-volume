#!/usr/bin/env python3
"""
Environment validation script.
Checks that all required environment variables are set.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import validate_environment

def main():
    """Run environment validation."""
    print("🔍 Validating environment configuration...\n")
    
    results = validate_environment()
    
    if results['valid']:
        print("✅ Environment validation passed!")
    else:
        print("❌ Environment validation failed!")
        print("\nErrors:")
        for error in results['errors']:
            print(f"  - {error}")
    
    if results['warnings']:
        print("\n⚠️  Warnings:")
        for warning in results['warnings']:
            print(f"  - {warning}")
    
    if results['missing_required']:
        print("\n❌ Missing required variables:")
        for var in results['missing_required']:
            print(f"  - {var}")
    
    if results['missing_optional']:
        print("\nℹ️  Missing optional variables:")
        for var in results['missing_optional']:
            print(f"  - {var}")
    
    print("\n💡 Tip: Copy env.example to .env and fill in your values")
    
    return 0 if results['valid'] else 1

if __name__ == '__main__':
    sys.exit(main())

