#!/usr/bin/env python3
"""
Database Setup Script for Exchange Rate Bot
Creates the necessary database and tables for storing exchange rates
"""

import mysql.connector
import os
import sys
import json

# Load configuration from JSON file
CONFIG_FILE = 'my.json'

def load_config():
    """Load configuration from my.json file"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{CONFIG_FILE}' not found!")
        print("Please create my.json from my.json.example")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing {CONFIG_FILE}: {e}")
        sys.exit(1)

# Load configuration
config = load_config()
db_config = config.get('database', {})

# MySQL Configuration
DB_HOST = db_config.get('host', 'localhost')
DB_USER = db_config.get('user', 'remote')
DB_PASSWORD = db_config.get('password', '')
DB_NAME = db_config.get('database', 'exchange_rates')
DB_SOCKET = db_config.get('socket', '/run/mysqld/mysqld.sock')


def get_connection(use_database=False):
    """Get MySQL connection"""
    try:
        if os.path.exists(DB_SOCKET):
            conn = mysql.connector.connect(
                user=DB_USER,
                password=DB_PASSWORD,
                unix_socket=DB_SOCKET
            )
        else:
            conn = mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD
            )

        if use_database:
            conn.database = DB_NAME

        return conn
    except mysql.connector.Error as e:
        print(f"Error connecting to MySQL: {e}")
        sys.exit(1)


def create_database():
    """Create the exchange_rates database if it doesn't exist"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Check if database exists
        cursor.execute("SHOW DATABASES LIKE %s", (DB_NAME,))
        result = cursor.fetchone()

        if result:
            print(f"Database '{DB_NAME}' already exists")
        else:
            # Create database
            cursor.execute(f"CREATE DATABASE `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"Database '{DB_NAME}' created successfully")

        conn.commit()

    except mysql.connector.Error as e:
        print(f"Error creating database: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


def create_tables():
    """Create the necessary tables"""
    conn = get_connection(use_database=True)
    cursor = conn.cursor()

    try:
        # Create exchange_rates table
        create_table_query = """
        CREATE TABLE IF NOT EXISTS exchange_rates (
            id INT AUTO_INCREMENT PRIMARY KEY,
            location VARCHAR(100) NOT NULL,
            currency VARCHAR(10) NOT NULL,
            we_sell_rate DECIMAL(10, 4) NOT NULL COMMENT 'Rate at which money changer sells to customer (green column)',
            we_buy_rate DECIMAL(10, 4) NOT NULL COMMENT 'Rate at which money changer buys from customer (red column)',
            timestamp DATETIME NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_location (location),
            INDEX idx_currency (currency),
            INDEX idx_timestamp (timestamp),
            INDEX idx_location_currency_timestamp (location, currency, timestamp)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        COMMENT='Exchange rates from Jalin & Duta money changers - both buy and sell rates'
        """

        cursor.execute(create_table_query)
        print("Table 'exchange_rates' created successfully (or already exists)")

        # Create a view for latest rates
        create_view_query = """
        CREATE OR REPLACE VIEW latest_exchange_rates AS
        SELECT
            location,
            currency,
            we_sell_rate,
            we_buy_rate,
            timestamp
        FROM exchange_rates e1
        WHERE timestamp = (
            SELECT MAX(timestamp)
            FROM exchange_rates e2
            WHERE e1.location = e2.location
            AND e1.currency = e2.currency
        )
        ORDER BY location, currency
        """

        cursor.execute(create_view_query)
        print("View 'latest_exchange_rates' created successfully")

        conn.commit()

    except mysql.connector.Error as e:
        print(f"Error creating tables: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


def show_table_info():
    """Display information about the created tables"""
    conn = get_connection(use_database=True)
    cursor = conn.cursor()

    try:
        print("\n" + "=" * 60)
        print("Table Structure:")
        print("=" * 60)

        cursor.execute("DESCRIBE exchange_rates")
        columns = cursor.fetchall()

        print("\nTable: exchange_rates")
        print("-" * 60)
        print(f"{'Field':<20} {'Type':<20} {'Null':<5} {'Key':<5}")
        print("-" * 60)

        for col in columns:
            field, type_, null, key, default, extra = col
            print(f"{field:<20} {type_:<20} {null:<5} {key:<5}")

        print("\n" + "=" * 60)
        print("Setup complete!")
        print("=" * 60)
        print(f"\nDatabase: {DB_NAME}")
        print("Tables: exchange_rates")
        print("Views: latest_exchange_rates")
        print("\nYou can now run the exchange_rate_bot.py script")

    except mysql.connector.Error as e:
        print(f"Error showing table info: {e}")
    finally:
        cursor.close()
        conn.close()


def main():
    """Main setup function"""
    print("Exchange Rate Bot - Database Setup")
    print("=" * 60)

    print(f"\nConfiguration:")
    print(f"  Database Host: {DB_HOST if not os.path.exists(DB_SOCKET) else 'localhost (socket)'}")
    print(f"  Database User: {DB_USER}")
    print(f"  Database Name: {DB_NAME}")
    print()

    # Create database
    print("Step 1: Creating database...")
    create_database()

    # Create tables
    print("\nStep 2: Creating tables and views...")
    create_tables()

    # Show table info
    print("\nStep 3: Verifying setup...")
    show_table_info()


if __name__ == "__main__":
    main()
