#!/usr/bin/env python3
"""
Exchange Rate Telegram Bot
Fetches GBP and EUR to MYR exchange rates from Jalin & Duta money changers
and posts to Telegram while recording in MySQL database.
"""

import os
import sys
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import mysql.connector
import logging
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('exchange_rate_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load configuration from JSON file
CONFIG_FILE = 'my.json'

def load_config():
    """Load configuration from my.json file"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file '{CONFIG_FILE}' not found!")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing {CONFIG_FILE}: {e}")
        sys.exit(1)

# Load configuration
config = load_config()

# URLs Configuration
BUKIT_BINTANG_URL = "https://www.jalinanduta.com/bukit-bintang/"
MASJID_INDIA_URL = "https://www.jalinanduta.com/masjid-india/"

# Telegram Configuration
TELEGRAM_BOT_TOKEN = config.get('telegram', {}).get('bot_token')
TELEGRAM_CHAT_ID = config.get('telegram', {}).get('chat_id')

# MySQL Configuration
db_config = config.get('database', {})
DB_HOST = db_config.get('host', 'localhost')
DB_USER = db_config.get('user', 'remote')
DB_PASSWORD = db_config.get('password', '')
DB_NAME = db_config.get('database', 'exchange_rates')
DB_SOCKET = db_config.get('socket', '/run/mysqld/mysqld.sock')


class ExchangeRateScraper:
    """Scraper for Jalin & Duta exchange rates"""

    def __init__(self):
        self.session = requests.Session()
        # More comprehensive headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        self.use_selenium = False

    def fetch_rates(self, url: str, location: str) -> Optional[Dict[str, float]]:
        """
        Fetch exchange rates from the given URL

        Args:
            url: URL to fetch rates from
            location: Location name (e.g., 'Bukit Bintang')

        Returns:
            Dictionary with currency codes as keys and rates as values
        """
        # Try requests first, fall back to Selenium if needed
        html_content = self._fetch_html_requests(url, location)

        if not html_content:
            logger.warning(f"Requests failed for {location}, trying Selenium...")
            html_content = self._fetch_html_selenium(url, location)

        if not html_content:
            logger.error(f"All fetch methods failed for {location}")
            return None

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            rates = self._parse_rates(soup)

            if rates:
                logger.info(f"Successfully fetched rates from {location}: {rates}")
            else:
                logger.warning(f"No rates found at {location}")
                # Save HTML for debugging
                debug_file = f"debug_{location.replace(' ', '_')}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                logger.info(f"Saved HTML to {debug_file} for inspection")

            return rates

        except Exception as e:
            logger.error(f"Unexpected error parsing rates from {location}: {e}")
            return None

    def _fetch_html_requests(self, url: str, location: str) -> Optional[str]:
        """Fetch HTML using requests library"""
        try:
            import time
            time.sleep(2)  # Polite delay

            logger.info(f"Fetching rates from {location}: {url}")
            response = self.session.get(url, timeout=30, allow_redirects=True)

            if response.status_code == 403:
                logger.warning(f"403 Forbidden from {location}, may need Selenium")
                return None

            response.raise_for_status()
            return response.text

        except requests.RequestException as e:
            logger.error(f"Requests error fetching from {location}: {e}")
            return None

    def _fetch_html_selenium(self, url: str, location: str) -> Optional[str]:
        """Fetch HTML using Selenium (for JavaScript-rendered content)"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            import time

            logger.info(f"Using Selenium to fetch {location}")

            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            driver = webdriver.Chrome(options=chrome_options)

            try:
                driver.get(url)
                # Wait for page to load
                time.sleep(5)

                # Wait for body to be present
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )

                html_content = driver.page_source
                return html_content
            finally:
                driver.quit()

        except ImportError:
            logger.error("Selenium not installed. Install with: pip install selenium")
            return None
        except Exception as e:
            logger.error(f"Selenium error for {location}: {e}")
            return None

    def _parse_rates(self, soup: BeautifulSoup) -> Dict[str, float]:
        """
        Parse exchange rates from the HTML
        Tries multiple methods to extract GBP and EUR "We Sell" rates
        """
        rates = {}

        try:
            logger.debug("Starting rate parsing...")

            # Method 1: Look for tables with exchange rates
            tables = soup.find_all('table')
            logger.debug(f"Found {len(tables)} tables")

            for table_idx, table in enumerate(tables):
                rows = table.find_all('tr')

                # First, identify which column is "We Sell"
                header_row = rows[0] if rows else None
                we_sell_col_idx = None

                if header_row:
                    headers = header_row.find_all(['th', 'td'])
                    for idx, header in enumerate(headers):
                        header_text = header.get_text(strip=True).upper()
                        if 'WE SELL' in header_text or 'SELL' in header_text:
                            we_sell_col_idx = idx
                            logger.debug(f"Found 'We Sell' column at index {idx}")
                            break

                # Parse data rows
                for row in rows[1:]:  # Skip header
                    cols = row.find_all(['td', 'th'])
                    if len(cols) < 2:
                        continue

                    # Look for currency code in first column
                    currency_cell = cols[0].get_text(strip=True).upper()
                    currency = None

                    # Check if this is GBP or EUR
                    if 'GBP' in currency_cell or 'POUND' in currency_cell or 'STERLING' in currency_cell or 'BRITAIN' in currency_cell:
                        currency = 'GBP'
                    elif 'EUR' in currency_cell or 'EURO' in currency_cell:
                        currency = 'EUR'

                    if not currency:
                        continue

                    # Extract rate from "We Sell" column or try all columns
                    if we_sell_col_idx and we_sell_col_idx < len(cols):
                        rate = self._extract_number(cols[we_sell_col_idx].get_text(strip=True))
                        if rate:
                            rates[currency] = rate
                            logger.info(f"Found {currency} rate: {rate} (from We Sell column)")
                    else:
                        # Try all columns if We Sell column not identified
                        for col_idx, col in enumerate(cols[1:], 1):
                            rate = self._extract_number(col.get_text(strip=True))
                            if rate and 2.0 < rate < 10.0:  # Reasonable MYR exchange rate range
                                rates[currency] = rate
                                logger.info(f"Found {currency} rate: {rate} (from column {col_idx})")
                                break

            # Method 2: Look for WordPress/custom layouts with classes
            if not rates:
                logger.debug("Trying method 2: Looking for div/span elements...")

                # Common class names for currency rate displays
                possible_classes = ['rate', 'price', 'currency', 'exchange', 'forex', 'money']

                for class_name in possible_classes:
                    elements = soup.find_all(['div', 'span', 'p'], class_=lambda x: x and class_name in str(x).lower())

                    for element in elements:
                        text = element.get_text(strip=True).upper()

                        if ('GBP' in text or 'POUND' in text) and 'GBP' not in rates:
                            rate = self._extract_number(text)
                            if rate:
                                rates['GBP'] = rate
                                logger.info(f"Found GBP rate: {rate} (from {class_name} element)")

                        if ('EUR' in text or 'EURO' in text) and 'EUR' not in rates:
                            rate = self._extract_number(text)
                            if rate:
                                rates['EUR'] = rate
                                logger.info(f"Found EUR rate: {rate} (from {class_name} element)")

            # Method 3: Look for any text containing currency and rates
            if not rates:
                logger.debug("Trying method 3: Full text search...")
                all_text = soup.get_text()

                # Look for patterns like "GBP 5.85" or "EUR: 5.20"
                import re
                gbp_pattern = r'(?:GBP|POUND|STERLING)[\s:]*(\d+\.?\d*)'
                eur_pattern = r'(?:EUR|EURO)[\s:]*(\d+\.?\d*)'

                if 'GBP' not in rates:
                    gbp_match = re.search(gbp_pattern, all_text, re.IGNORECASE)
                    if gbp_match:
                        rate = float(gbp_match.group(1))
                        if 2.0 < rate < 10.0:
                            rates['GBP'] = rate
                            logger.info(f"Found GBP rate: {rate} (from text search)")

                if 'EUR' not in rates:
                    eur_match = re.search(eur_pattern, all_text, re.IGNORECASE)
                    if eur_match:
                        rate = float(eur_match.group(1))
                        if 2.0 < rate < 10.0:
                            rates['EUR'] = rate
                            logger.info(f"Found EUR rate: {rate} (from text search)")

            return rates

        except Exception as e:
            logger.error(f"Error parsing HTML structure: {e}", exc_info=True)
            return {}

    def _extract_number(self, text: str) -> Optional[float]:
        """Extract a floating point number from text"""
        import re
        # Find all numbers with optional decimal points
        matches = re.findall(r'\d+\.?\d*', text)
        for match in matches:
            try:
                num = float(match)
                if num > 1:  # Reasonable exchange rate
                    return num
            except ValueError:
                continue
        return None


class DatabaseManager:
    """Manager for MySQL database operations"""

    def __init__(self):
        self.connection = None

    def connect(self):
        """Establish database connection"""
        try:
            if os.path.exists(DB_SOCKET):
                self.connection = mysql.connector.connect(
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    unix_socket=DB_SOCKET
                )
            else:
                self.connection = mysql.connector.connect(
                    host=DB_HOST,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME
                )
            logger.info("Successfully connected to database")
        except mysql.connector.Error as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("Database connection closed")

    def save_rates(self, location: str, rates: Dict[str, float]):
        """
        Save exchange rates to database

        Args:
            location: Location name (e.g., 'Bukit Bintang')
            rates: Dictionary of currency codes and rates
        """
        if not self.connection or not self.connection.is_connected():
            self.connect()

        cursor = self.connection.cursor()
        timestamp = datetime.now()

        try:
            for currency, rate in rates.items():
                query = """
                    INSERT INTO exchange_rates
                    (location, currency, rate, timestamp)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(query, (location, currency, rate, timestamp))

            self.connection.commit()
            logger.info(f"Saved {len(rates)} rates for {location} to database")

        except mysql.connector.Error as e:
            logger.error(f"Error saving rates to database: {e}")
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def get_latest_rates(self) -> List[Dict]:
        """Get the latest rates for each location and currency"""
        if not self.connection or not self.connection.is_connected():
            self.connect()

        cursor = self.connection.cursor(dictionary=True)

        try:
            query = """
                SELECT location, currency, rate, timestamp
                FROM exchange_rates
                WHERE timestamp IN (
                    SELECT MAX(timestamp)
                    FROM exchange_rates
                    GROUP BY location, currency
                )
                ORDER BY location, currency
            """
            cursor.execute(query)
            results = cursor.fetchall()
            return results

        except mysql.connector.Error as e:
            logger.error(f"Error fetching latest rates: {e}")
            return []
        finally:
            cursor.close()


class TelegramNotifier:
    """Telegram bot notifier"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, message: str) -> bool:
        """
        Send message to Telegram chat

        Args:
            message: Message text to send

        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }

            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()

            logger.info("Message sent to Telegram successfully")
            return True

        except requests.RequestException as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False


def format_rate_message(all_rates: Dict[str, Dict[str, float]]) -> str:
    """
    Format exchange rates into a Telegram message

    Args:
        all_rates: Dictionary with location as key and rates dict as value

    Returns:
        Formatted message string
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    message = f"<b>💱 Exchange Rates Update</b>\n"
    message += f"📅 {timestamp}\n\n"

    for location, rates in all_rates.items():
        message += f"<b>📍 {location}</b>\n"

        if 'GBP' in rates:
            message += f"  🇬🇧 GBP → MYR: <b>RM {rates['GBP']:.4f}</b>\n"

        if 'EUR' in rates:
            message += f"  🇪🇺 EUR → MYR: <b>RM {rates['EUR']:.4f}</b>\n"

        if not rates:
            message += "  ⚠️ No rates available\n"

        message += "\n"

    message += "<i>We Sell rates from Jalin &amp; Duta Money Changers</i>"

    return message


def main():
    """Main execution function"""
    logger.info("=" * 50)
    logger.info("Exchange Rate Bot started")
    logger.info("=" * 50)

    # Validate configuration
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in environment variables")
        sys.exit(1)

    # Initialize components
    scraper = ExchangeRateScraper()
    db_manager = DatabaseManager()
    telegram = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

    all_rates = {}

    try:
        # Connect to database
        db_manager.connect()

        # Fetch rates from both locations
        locations = [
            (BUKIT_BINTANG_URL, "Bukit Bintang"),
            (MASJID_INDIA_URL, "Masjid India")
        ]

        for url, location in locations:
            rates = scraper.fetch_rates(url, location)
            if rates:
                all_rates[location] = rates
                # Save to database
                db_manager.save_rates(location, rates)
            else:
                all_rates[location] = {}
                logger.warning(f"No rates fetched for {location}")

        # Format and send Telegram message
        if all_rates:
            message = format_rate_message(all_rates)
            telegram.send_message(message)
        else:
            error_msg = "⚠️ Failed to fetch any exchange rates. Please check the logs."
            telegram.send_message(error_msg)
            logger.error("No rates were successfully fetched")

        logger.info("Exchange rate bot completed successfully")

    except Exception as e:
        logger.error(f"Fatal error in main execution: {e}", exc_info=True)
        error_msg = f"❌ Exchange Rate Bot Error:\n{str(e)}"
        telegram.send_message(error_msg)
        sys.exit(1)

    finally:
        db_manager.disconnect()


if __name__ == "__main__":
    main()
