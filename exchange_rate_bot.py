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
GOOGLE_FINANCE_GBP_URL = "https://www.google.com/finance/quote/GBP-MYR"
GOOGLE_FINANCE_EUR_URL = "https://www.google.com/finance/quote/EUR-MYR"
GOOGLE_FINANCE_IDR_URL = "https://www.google.com/finance/quote/IDR-MYR"
GOOGLE_FINANCE_TRY_URL = "https://www.google.com/finance/quote/TRY-MYR"
BUKIT_BINTANG_URL = "https://www.jalinanduta.com/bukit-bintang/"
MASJID_INDIA_URL = "https://www.jalinanduta.com/masjid-india/"
MYMONEYMASTER_URL = "http://www.mymoneymaster.com.my/Home/full_rate_board"

# Card Network Exchange Rate URLs (ferates.com)
VISA_RATES_URL = "https://ferates.com/visa/myr"
MASTERCARD_RATES_URL = "https://ferates.com/mastercard/myr"

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

    def fetch_google_finance_rates(self) -> tuple[Optional[Dict[str, Dict[str, float]]], Optional[datetime]]:
        """
        Fetch exchange rates from Google Finance for GBP, EUR, IDR, and TRY

        Returns:
            Tuple of (rates_dict, timestamp)
            rates_dict: Dictionary with currency codes as keys and {'we_sell': rate, 'we_buy': rate} as values
            timestamp: Current datetime (Google Finance doesn't provide last update time)
        """
        rates = {}

        try:
            # Define currencies to fetch
            currencies = [
                ('GBP', GOOGLE_FINANCE_GBP_URL),
                ('EUR', GOOGLE_FINANCE_EUR_URL),
                ('IDR', GOOGLE_FINANCE_IDR_URL),
                ('TRY', GOOGLE_FINANCE_TRY_URL)
            ]

            # Fetch each currency
            for currency_code, url in currencies:
                html_content = self._fetch_html_requests(url, f"Google Finance {currency_code}")
                if html_content:
                    rate = self._parse_google_finance(html_content, currency_code)
                    if rate:
                        # Google Finance shows the exchange rate, which is what we "sell" MYR for
                        # Standardize rates to match other sources
                        if currency_code == 'IDR':
                            # Google shows per 1 IDR, we want per 1,000,000 IDR
                            rate = rate * 1000000
                            logger.info(f"Standardized Google Finance IDR rate to per 1,000,000: {rate}")
                        elif currency_code == 'TRY':
                            # Google shows per 1 TRY, we want per 100 TRY
                            rate = rate * 100
                            logger.info(f"Standardized Google Finance TRY rate to per 100: {rate}")

                        # For consistency with other sources, we'll use the same rate for both buy and sell
                        rates[currency_code] = {
                            'we_sell': rate,
                            'we_buy': rate
                        }

            if rates:
                logger.info(f"Successfully fetched Google Finance rates: {rates}")
                return rates, datetime.now()
            else:
                logger.warning("No rates found from Google Finance")
                return None, None

        except Exception as e:
            logger.error(f"Error fetching Google Finance rates: {e}")
            return None, None

    def fetch_card_rates(self, card_network: str) -> tuple[Optional[Dict[str, Dict[str, float]]], Optional[datetime]]:
        """
        Fetch exchange rates from card networks (Visa/Mastercard) via ferates.com

        Args:
            card_network: Either 'Visa' or 'Mastercard'

        Returns:
            Tuple of (rates_dict, timestamp)
            rates_dict: Dictionary with currency codes as keys and {'we_sell': rate, 'we_buy': rate} as values
            timestamp: Current datetime
        """
        rates = {}

        try:
            # Select URL based on card network
            if card_network.lower() == 'visa':
                url = VISA_RATES_URL
            elif card_network.lower() == 'mastercard':
                url = MASTERCARD_RATES_URL
            else:
                logger.error(f"Unknown card network: {card_network}")
                return None, None

            logger.info(f"Fetching {card_network} rates from {url}")

            # Fetch HTML content
            html_content = self._fetch_html_requests(url, f"{card_network} Rates")
            if not html_content:
                logger.warning(f"Failed to fetch {card_network} rates")
                return None, None

            # Parse the rates
            rates = self._parse_card_rates(html_content, card_network)

            if rates:
                logger.info(f"Successfully fetched {card_network} rates: {rates}")
                return rates, datetime.now()
            else:
                logger.warning(f"No rates found from {card_network}")
                return None, None

        except Exception as e:
            logger.error(f"Error fetching {card_network} rates: {e}")
            return None, None

    def fetch_rates(self, url: str, location: str) -> tuple[Optional[Dict[str, Dict[str, float]]], Optional[datetime]]:
        """
        Fetch exchange rates from the given URL

        Args:
            url: URL to fetch rates from
            location: Location name (e.g., 'Bukit Bintang')

        Returns:
            Tuple of (rates_dict, timestamp)
            rates_dict: Dictionary with currency codes as keys and rates as values
            timestamp: datetime when rates were last updated (None for Jalin & Duta, uses current time)
        """
        # Try requests first, fall back to Selenium if needed
        html_content = self._fetch_html_requests(url, location)

        if not html_content:
            logger.warning(f"Requests failed for {location}, trying Selenium...")
            html_content = self._fetch_html_selenium(url, location)

        if not html_content:
            logger.error(f"All fetch methods failed for {location}")
            return None, None

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            rates, rate_timestamp = self._parse_rates(soup)

            if rates:
                logger.info(f"Successfully fetched rates from {location}: {rates}")
            else:
                logger.warning(f"No rates found at {location}")
                # Save HTML for debugging
                debug_file = f"debug_{location.replace(' ', '_')}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                logger.info(f"Saved HTML to {debug_file} for inspection")

            return rates, rate_timestamp

        except Exception as e:
            logger.error(f"Unexpected error parsing rates from {location}: {e}")
            return None, None

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

    def _parse_rates(self, soup: BeautifulSoup) -> tuple[Dict[str, Dict[str, float]], Optional[datetime]]:
        """
        Parse exchange rates from the HTML
        Extracts both "We Sell" (green) and "We Buy" (red) rates for GBP and EUR

        Returns:
            Tuple of (rates_dict, timestamp)
            rates_dict: Dictionary with currency codes as keys and dict of {'we_sell': rate, 'we_buy': rate} as values
            timestamp: datetime for MyMoneyMaster, None for Jalin & Duta (will use current time)
        """
        rates = {}

        try:
            logger.debug("Starting rate parsing...")

            # Check if this is MyMoneyMaster website (different structure)
            if soup.find('tr', class_='filtersearch'):
                logger.debug("Detected MyMoneyMaster website structure")
                rates, rate_timestamp = self._parse_mymoneymaster(soup)
                if rates:
                    return rates, rate_timestamp

            # Method 1: Look for tables with exchange rates (Jalin & Duta)
            tables = soup.find_all('table')
            logger.debug(f"Found {len(tables)} tables")

            for table_idx, table in enumerate(tables):
                rows = table.find_all('tr')

                # Parse data rows - look for GBP and EUR
                for row in rows:
                    cols = row.find_all(['td', 'th'])
                    if len(cols) < 4:  # Need at least 4 columns
                        continue

                    # Look for currency code - check both first and second columns
                    currency = None
                    for check_col_idx in [0, 1]:
                        if check_col_idx >= len(cols):
                            continue
                        currency_cell = cols[check_col_idx].get_text(strip=True).upper()

                        # Check for supported currencies
                        if 'GBP' in currency_cell or 'POUND' in currency_cell or 'STERLING' in currency_cell or 'BRITAIN' in currency_cell:
                            currency = 'GBP'
                            break
                        elif 'EUR' in currency_cell or 'EURO' in currency_cell:
                            currency = 'EUR'
                            break
                        elif 'IDR' in currency_cell or 'RUPIAH' in currency_cell or 'INDONESIA' in currency_cell:
                            currency = 'IDR'
                            break
                        elif 'TRY' in currency_cell or 'LIRA' in currency_cell or 'TURKISH' in currency_cell or 'TURKEY' in currency_cell:
                            currency = 'TRY'
                            break

                    if not currency:
                        continue

                    # Look for both "We Sell" and "We Buy" rates
                    # Structure: [Flag, Currency Code, Currency Name, Unit, We Sell (green), We Buy (red)]
                    we_sell_rate = None
                    we_buy_rate = None

                    # Try to find cells with table-green-color (We Sell) and table-red-color (We Buy)
                    for col in cols:
                        col_classes = col.get('class')
                        if col_classes:
                            if 'table-green-color' in col_classes:
                                rate = self._extract_number(col.get_text(strip=True))
                                if rate:
                                    we_sell_rate = rate
                                    logger.debug(f"Found {currency} We Sell rate: {rate} (from table-green-color)")
                            elif 'table-red-color' in col_classes:
                                rate = self._extract_number(col.get_text(strip=True))
                                if rate:
                                    we_buy_rate = rate
                                    logger.debug(f"Found {currency} We Buy rate: {rate} (from table-red-color)")

                    # If we found both rates with CSS classes, use them
                    if we_sell_rate and we_buy_rate:
                        rates[currency] = {
                            'we_sell': we_sell_rate,
                            'we_buy': we_buy_rate
                        }
                        logger.info(f"Found {currency} rates: We Sell={we_sell_rate}, We Buy={we_buy_rate}")
                    # Fallback: if classes not found, try column indices (4=We Sell, 5=We Buy)
                    elif len(cols) >= 6:
                        we_sell_rate = self._extract_number(cols[4].get_text(strip=True))
                        we_buy_rate = self._extract_number(cols[5].get_text(strip=True))
                        if we_sell_rate and we_buy_rate and 2.0 < we_sell_rate < 10.0 and 2.0 < we_buy_rate < 10.0:
                            rates[currency] = {
                                'we_sell': we_sell_rate,
                                'we_buy': we_buy_rate
                            }
                            logger.info(f"Found {currency} rates (fallback): We Sell={we_sell_rate}, We Buy={we_buy_rate}")

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

            # Jalin & Duta don't have timestamps, return None
            return rates, None

        except Exception as e:
            logger.error(f"Error parsing HTML structure: {e}", exc_info=True)
            return {}, None

    def _parse_mymoneymaster(self, soup: BeautifulSoup) -> tuple[Dict[str, Dict[str, float]], Optional[datetime]]:
        """
        Parse exchange rates from MyMoneyMaster website

        MyMoneyMaster structure:
        - Row with class "filtersearch" containing currency info
        - td[0]: Currency name and code (e.g., "European Union Euro Dollar (EUR)")
        - td[1]: We Buy rate (they buy from customer)
        - td[2]: We Sell rate (they sell to customer)
        - td[3]: Timestamp (e.g., "at 03:07 PM")

        Returns:
            Tuple of (rates_dict, timestamp)
            rates_dict: Dictionary with currency codes as keys and dict of {'we_sell': rate, 'we_buy': rate} as values
            timestamp: datetime object parsed from the "Last Updated" field
        """
        rates = {}
        rate_timestamp = None

        try:
            # Find all currency rows
            currency_rows = soup.find_all('tr', class_='filtersearch')
            logger.debug(f"Found {len(currency_rows)} currency rows in MyMoneyMaster")

            for row in currency_rows:
                cols = row.find_all('td')
                if len(cols) < 4:
                    continue

                # Extract currency code from first column
                currency_text = cols[0].get_text(strip=True).upper()
                currency = None

                # Check for supported currencies
                if 'GBP' in currency_text or 'POUND' in currency_text or 'STERLING' in currency_text:
                    currency = 'GBP'
                elif 'EUR' in currency_text or 'EURO' in currency_text:
                    currency = 'EUR'
                elif 'IDR' in currency_text or 'RUPIAH' in currency_text or 'INDONESIA' in currency_text:
                    currency = 'IDR'
                elif 'TRY' in currency_text or 'TUR' in currency_text or 'LIRA' in currency_text or 'TURKISH' in currency_text or 'TURKEY' in currency_text:
                    currency = 'TRY'

                if not currency:
                    continue

                # Extract We Buy rate (column 1) and We Sell rate (column 2)
                we_buy_rate = self._extract_number(cols[1].get_text(strip=True))
                we_sell_rate = self._extract_number(cols[2].get_text(strip=True))

                # Standardize TRY rates (MyMoneyMaster shows per 1 TRY, we want per 100 TRY)
                if currency == 'TRY' and we_buy_rate and we_sell_rate:
                    we_buy_rate = we_buy_rate * 100
                    we_sell_rate = we_sell_rate * 100
                    logger.info(f"Standardized MyMoneyMaster TRY rates to per 100: We Sell={we_sell_rate}, We Buy={we_buy_rate}")

                # Extract timestamp from column 3 (e.g., "at 03:07 PM")
                if len(cols) >= 4 and not rate_timestamp:
                    timestamp_text = cols[3].get_text(strip=True)
                    rate_timestamp = self._parse_mymoneymaster_timestamp(timestamp_text)

                if we_buy_rate and we_sell_rate:
                    rates[currency] = {
                        'we_sell': we_sell_rate,
                        'we_buy': we_buy_rate
                    }
                    logger.info(f"Found {currency} rates: We Sell={we_sell_rate}, We Buy={we_buy_rate}")

            if rate_timestamp:
                logger.info(f"MyMoneyMaster rates last updated: {rate_timestamp}")

            return rates, rate_timestamp

        except Exception as e:
            logger.error(f"Error parsing MyMoneyMaster rates: {e}", exc_info=True)
            return {}, None

    def _parse_mymoneymaster_timestamp(self, timestamp_text: str) -> Optional[datetime]:
        """
        Parse MyMoneyMaster timestamp format (e.g., "at 03:07 PM")

        Returns:
            datetime object with today's date and the parsed time
        """
        try:
            import re
            from datetime import datetime

            # Extract time from text like "at 03:07 PM"
            match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)', timestamp_text, re.IGNORECASE)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2))
                ampm = match.group(3).upper()

                # Convert to 24-hour format
                if ampm == 'PM' and hour != 12:
                    hour += 12
                elif ampm == 'AM' and hour == 12:
                    hour = 0

                # Create datetime with today's date and extracted time
                now = datetime.now()
                parsed_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                logger.debug(f"Parsed timestamp '{timestamp_text}' as {parsed_time}")
                return parsed_time

            logger.warning(f"Could not parse timestamp: {timestamp_text}")
            return None

        except Exception as e:
            logger.error(f"Error parsing timestamp '{timestamp_text}': {e}")
            return None

    def _parse_google_finance(self, html_content: str, currency: str) -> Optional[float]:
        """
        Parse exchange rate from Google Finance

        Args:
            html_content: HTML content from Google Finance page
            currency: Currency code (GBP or EUR)

        Returns:
            Exchange rate as float, or None if not found
        """
        try:
            import re

            # Google Finance uses class "YMlKec fxKbKc" for the rate value
            match = re.search(r'"YMlKec fxKbKc">([0-9.]+)', html_content)
            if match:
                rate = float(match.group(1))
                logger.info(f"Found Google Finance {currency} rate: {rate}")
                return rate

            logger.warning(f"Could not find Google Finance rate for {currency}")
            return None

        except Exception as e:
            logger.error(f"Error parsing Google Finance rate for {currency}: {e}")
            return None

    def _parse_card_rates(self, html_content: str, card_network: str) -> Dict[str, Dict[str, float]]:
        """
        Parse exchange rates from ferates.com for card networks

        Args:
            html_content: HTML content from ferates.com
            card_network: Either 'Visa' or 'Mastercard'

        Returns:
            Dictionary with currency codes as keys and {'we_sell': rate, 'we_buy': rate} as values
        """
        rates = {}

        try:
            from bs4 import BeautifulSoup
            import re

            soup = BeautifulSoup(html_content, 'html.parser')

            # ferates.com shows rates in a table format
            # We need to find rows for GBP, EUR, TRY, and IDR
            # The format is typically: "Currency Name (CODE)" | Rate to MYR

            # Find all table rows
            rows = soup.find_all('tr')

            for row in rows:
                cols = row.find_all(['td', 'th'])
                if len(cols) < 2:
                    continue

                # Extract currency code from first column
                currency_text = cols[0].get_text(strip=True).upper()
                currency = None

                # Check for supported currencies
                if 'GBP' in currency_text or 'POUND' in currency_text or 'STERLING' in currency_text or 'BRITAIN' in currency_text:
                    currency = 'GBP'
                elif 'EUR' in currency_text or 'EURO' in currency_text:
                    currency = 'EUR'
                elif 'IDR' in currency_text or 'RUPIAH' in currency_text or 'INDONESIA' in currency_text:
                    currency = 'IDR'
                elif 'TRY' in currency_text or 'LIRA' in currency_text or 'TURKISH' in currency_text or 'TURKEY' in currency_text or 'TUR' in currency_text:
                    currency = 'TRY'

                if not currency:
                    continue

                # Extract rate from second column
                rate_text = cols[1].get_text(strip=True)
                rate = self._extract_number(rate_text)

                if rate:
                    # Standardize rates
                    # ferates.com typically shows rate per 1 unit of foreign currency to MYR
                    # For MYR to foreign currency, we need to invert: 1/rate
                    # This gives us how many foreign currency units per 1 MYR

                    # However, since the page is for "visa/myr" or "mastercard/myr"
                    # it should show MYR to other currencies
                    # We need to verify the format by checking the actual data

                    # For now, let's assume it shows foreign currency to MYR (like "1 GBP = X MYR")
                    # We want MYR to foreign currency, so we invert
                    myr_to_foreign = 1.0 / rate if rate > 0 else 0

                    # Apply standardization for IDR and TRY
                    if currency == 'IDR':
                        # Convert to per 1,000,000 IDR
                        myr_to_foreign = myr_to_foreign * 1000000
                        logger.info(f"Standardized {card_network} IDR rate to per 1,000,000: {myr_to_foreign}")
                    elif currency == 'TRY':
                        # Convert to per 100 TRY
                        myr_to_foreign = myr_to_foreign * 100
                        logger.info(f"Standardized {card_network} TRY rate to per 100: {myr_to_foreign}")

                    # Card networks use the same rate for buy and sell (they apply their own markup)
                    rates[currency] = {
                        'we_sell': rate,  # Use the original rate (foreign to MYR)
                        'we_buy': rate
                    }
                    logger.info(f"Found {card_network} {currency} rate: {rate}")

            return rates

        except Exception as e:
            logger.error(f"Error parsing {card_network} rates: {e}", exc_info=True)
            return {}

    def _extract_number(self, text: str) -> Optional[float]:
        """Extract a floating point number from text"""
        import re
        # Find all numbers with optional decimal points
        matches = re.findall(r'\d+\.?\d*', text)
        for match in matches:
            try:
                num = float(match)
                if num > 0:  # Any positive number is valid
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

    def save_rates(self, location: str, rates: Dict[str, Dict[str, float]], rate_timestamp: Optional[datetime] = None):
        """
        Save exchange rates to database

        Args:
            location: Location name (e.g., 'Bukit Bintang')
            rates: Dictionary with currency codes as keys and {'we_sell': rate, 'we_buy': rate} as values
            rate_timestamp: Optional timestamp from source (MyMoneyMaster), uses current time if None
        """
        if not self.connection or not self.connection.is_connected():
            self.connect()

        cursor = self.connection.cursor()
        # Use provided timestamp if available, otherwise use current time
        timestamp = rate_timestamp if rate_timestamp is not None else datetime.now()

        try:
            for currency, rate_data in rates.items():
                query = """
                    INSERT INTO exchange_rates
                    (location, currency, we_sell_rate, we_buy_rate, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    location,
                    currency,
                    rate_data['we_sell'],
                    rate_data['we_buy'],
                    timestamp
                ))

            self.connection.commit()
            timestamp_source = "from source" if rate_timestamp else "current time"
            logger.info(f"Saved {len(rates)} currency rates (both buy and sell) for {location} to database with timestamp {timestamp} ({timestamp_source})")

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


def format_rate_message(all_rates: Dict[str, Dict[str, Dict[str, float]]]) -> str:
    """
    Format exchange rates into a Telegram message
    Displays only "We Sell" rates (the rate for buying foreign currency)

    Args:
        all_rates: Dictionary with location as key and rates dict as value
                  Each rate dict has currency code as key and {'we_sell': rate, 'we_buy': rate} as value

    Returns:
        Formatted message string
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    message = f"<b>💱 Exchange Rates We Sell Rate</b>\n"
    message += f"📅 {timestamp}\n\n"

    # Define the order: Google Finance, then Mastercard, Visa, then other locations
    priority_order = ["Google Finance", "Mastercard", "Visa"]

    # First, display priority locations (Google Finance, Mastercard, Visa)
    for location in priority_order:
        if location in all_rates:
            rates = all_rates[location]

            # Use card emoji for card networks
            if location == "Mastercard":
                message += f"<b>💳 {location}</b>\n"
            elif location == "Visa":
                message += f"<b>💳 {location}</b>\n"
            else:
                message += f"<b>📍 {location}</b>\n"

            if 'GBP' in rates:
                message += f"  🇬🇧 MYR → 1 GBP : <b>RM {rates['GBP']['we_sell']:.4f}</b>\n"

            if 'EUR' in rates:
                message += f"  🇪🇺 MYR → 1 EUR : <b>RM {rates['EUR']['we_sell']:.4f}</b>\n"

            if 'IDR' in rates:
                message += f"  🇮🇩 MYR → 1mil IDR : <b>RM {rates['IDR']['we_sell']:.4f}</b>\n"

            if 'TRY' in rates:
                message += f"  🇹🇷 MYR → 100 TRY : <b>RM {rates['TRY']['we_sell']:.4f}</b>\n"

            if not rates:
                message += "  ⚠️ No rates available\n"

            message += "\n"

    # Then display other locations (money changers)
    for location, rates in all_rates.items():
        if location not in priority_order:
            message += f"<b>📍 {location}</b>\n"

            if 'GBP' in rates:
                message += f"  🇬🇧 MYR → 1 GBP : <b>RM {rates['GBP']['we_sell']:.4f}</b>\n"

            if 'EUR' in rates:
                message += f"  🇪🇺 MYR → 1 EUR : <b>RM {rates['EUR']['we_sell']:.4f}</b>\n"

            if 'IDR' in rates:
                message += f"  🇮🇩 MYR → 1mil IDR : <b>RM {rates['IDR']['we_sell']:.4f}</b>\n"

            if 'TRY' in rates:
                message += f"  🇹🇷 MYR → 100 TRY : <b>RM {rates['TRY']['we_sell']:.4f}</b>\n"

            if not rates:
                message += "  ⚠️ No rates available\n"

            message += "\n"

    message += "<i>We Sell rates from Google Finance, Mastercard, Visa, JalinanDuta and MyMoneyMaster</i>\n"
    message += "<i>(Rate for buying foreign currency with MYR)</i>"

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

        # Fetch Google Finance rates first
        google_rates, google_timestamp = scraper.fetch_google_finance_rates()
        if google_rates:
            all_rates["Google Finance"] = google_rates
            db_manager.save_rates("Google Finance", google_rates, google_timestamp)
        else:
            all_rates["Google Finance"] = {}
            logger.warning("No rates fetched from Google Finance")

        # Fetch Mastercard rates
        mastercard_rates, mastercard_timestamp = scraper.fetch_card_rates("Mastercard")
        if mastercard_rates:
            all_rates["Mastercard"] = mastercard_rates
            db_manager.save_rates("Mastercard", mastercard_rates, mastercard_timestamp)
        else:
            all_rates["Mastercard"] = {}
            logger.warning("No rates fetched from Mastercard")

        # Fetch Visa rates
        visa_rates, visa_timestamp = scraper.fetch_card_rates("Visa")
        if visa_rates:
            all_rates["Visa"] = visa_rates
            db_manager.save_rates("Visa", visa_rates, visa_timestamp)
        else:
            all_rates["Visa"] = {}
            logger.warning("No rates fetched from Visa")

        # Fetch rates from all other locations
        locations = [
            (BUKIT_BINTANG_URL, "JalinanDuta(Bukit Bintang)"),
            (MASJID_INDIA_URL, "JalinanDuta(Masjid India)"),
            (MYMONEYMASTER_URL, "MyMoneyMaster(Mid Valley)")
        ]

        for url, location in locations:
            rates, rate_timestamp = scraper.fetch_rates(url, location)
            if rates:
                all_rates[location] = rates
                # Save to database (pass timestamp if available from source)
                db_manager.save_rates(location, rates, rate_timestamp)
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
