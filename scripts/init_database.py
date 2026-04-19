# -*- coding: utf-8 -*-
"""
faster_qt Database Initialization Script

Usage:
    python scripts/init_database.py

Author: 江小猪
Date: 2026-04-19
"""

import psycopg2
from psycopg2 import sql
import sys
import os

# Database Configuration
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": "root",
    "dbname": "postgres"
}

TARGET_DB = "faster_qt"
TARGET_USER = "faster_qt"
TARGET_PASSWORD = "faster_qt123"


def test_connection():
    print("[TEST] Testing PostgreSQL connection...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"[OK] Connection success: {version}")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[FAIL] Connection failed: {e}")
        return False


def create_database():
    print(f"\n[STEP] Creating database '{TARGET_DB}'...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()
        
        cur.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (TARGET_DB,)
        )
        exists = cur.fetchone()
        
        if not exists:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(TARGET_DB)
            ))
            print(f"[OK] Database '{TARGET_DB}' created")
        else:
            print(f"[INFO] Database '{TARGET_DB}' already exists")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[FAIL] Create database failed: {e}")
        return False


def test_target_connection():
    print(f"\n[TEST] Testing target database connection...")
    try:
        target_config = DB_CONFIG.copy()
        target_config["dbname"] = TARGET_DB
        conn = psycopg2.connect(**target_config)
        cur = conn.cursor()
        
        cur.execute("SELECT current_database(), current_user;")
        result = cur.fetchone()
        print(f"[OK] Connected to database: {result[0]}, user: {result[1]}")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[FAIL] Connect to target database failed: {e}")
        return False


def check_timescaleDB():
    print(f"\n[INFO] Checking TimescaleDB extension...")
    try:
        target_config = DB_CONFIG.copy()
        target_config["dbname"] = TARGET_DB
        conn = psycopg2.connect(**target_config)
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM pg_extension WHERE extname = 'timescaledb';")
        result = cur.fetchone()
        
        if result:
            print(f"[OK] TimescaleDB installed: {result}")
        else:
            print(f"[INFO] TimescaleDB not installed (optional)")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[INFO] TimescaleDB check failed (optional): {e}")
        return True


def print_summary():
    print("\n" + "=" * 60)
    print("[INFO] Database Configuration Summary")
    print("=" * 60)
    print(f"  Host:       127.0.0.1")
    print(f"  Port:       5432")
    print(f"  Database:   {TARGET_DB}")
    print(f"  User:       {TARGET_USER}")
    print(f"  Password:   {TARGET_PASSWORD}")
    print(f"  Connection: postgresql://{TARGET_USER}:{TARGET_PASSWORD}@127.0.0.1:5432/{TARGET_DB}")
    print("=" * 60)
    print("\n[USAGE] In code:")
    print(f"  from src.data import DataStorage")
    print(f"  storage = DataStorage(")
    print(f"      db_url='postgresql://{TARGET_USER}:{TARGET_PASSWORD}@127.0.0.1:5432/{TARGET_DB}',")
    print(f"      redis_url='redis://127.0.0.1:6379'")
    print(f"  )")


def main():
    print("=" * 60)
    print("[INIT] faster_qt Database Initialization")
    print("=" * 60)
    
    if not test_connection():
        print("\n[FAIL] Cannot connect to PostgreSQL")
        sys.exit(1)
    
    if not create_database():
        sys.exit(1)
    
    if not test_target_connection():
        sys.exit(1)
    
    check_timescaleDB()
    print_summary()
    
    print("\n[OK] Database initialization complete!")


if __name__ == "__main__":
    main()