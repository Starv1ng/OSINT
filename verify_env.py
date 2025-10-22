#!/usr/bin/env python3
"""
OSINT envrionment checking
"""

import sys
import os
from pathlib import Path

def check_structure():
    print("📁 Checking structure...")
    
    required_dirs = [
        "OSINT/services/api/app/api/models",
        "OSINT/services/api/app/api/schemas", 
        "OSINT/services/api/app/api/routes",
        "OSINT/services/api/app/tasks",
        "OSINT/services/worker/tasks",
        "OSINT/infra",
        "OSINT/envs"
    ]
    
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"✅ {dir_path}")
        else:
            print(f"❌ {dir_path} - Lost")

def check_environment():
    print("\n🐍 Checking virtual environment...")
    print(f"Python executable: {sys.executable}")
    print(f"Virtual env: {hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)}")
    
    required_packages = [
        'fastapi', 'sqlalchemy', 'celery', 'redis', 
        'psycopg2', 'pydantic', 'alembic'
    ]
    
    print("\n📦 Installed Packages:")
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")

if __name__ == "__main__":
    check_structure()
    check_environment()
    print("\n🎯 Checking OK!")