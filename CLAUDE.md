# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based exchange rate monitoring bot that scrapes GBP, EUR, and TRY to MYR exchange rates from multiple Malaysian money changers (Google Finance, JalinanDuta, MyMoneyMaster), stores historical data in MySQL, and sends notifications via Telegram.

## Key Commands

### Running the Bot
```bash
# Must use the virtual environment
source /opt/venv/venv/bin/activate
python3 exchange_rate_bot.py
```

### Database Setup
```bash
# Initial setup - creates database, tables, and views
python3 setup_database.py
```

### Database Queries
```sql
-- View latest rates for all currencies and locations
SELECT * FROM latest_exchange_rates;

-- Check recent bot runs
SELECT * FROM exchange_rates WHERE DATE(timestamp) = CURDATE() ORDER BY timestamp DESC;
```

## Architecture

### Core Components

**exchange_rate_bot.py** - Main bot with three primary classes:

1. **ExchangeRateScraper** - Handles all web scraping with source-specific parsers
   - `fetch_google_finance_rates()` - Fetches GBP, EUR, TRY from Google Finance
   - `fetch_rates()` - Generic fetcher for JalinanDuta and MyMoneyMaster
   - `_parse_rates()` - Parses JalinanDuta HTML (looks for `table-green-color` and `table-red-color` CSS classes)
   - `_parse_mymoneymaster()` - Parses MyMoneyMaster HTML (finds rows with class `filtersearch`)
   - `_parse_google_finance()` - Parses Google Finance HTML (extracts from class `YMlKec fxKbKc`)
   - Uses requests by default, falls back to Selenium for JavaScript-heavy sites (403 errors)

2. **DatabaseManager** - MySQL operations
   - Connects via Unix socket (`/run/mysqld/mysqld.sock`) or TCP
   - `save_rates()` - Stores both "We Sell" and "We Buy" rates with timestamps
   - Handles timestamps: Google Finance and MyMoneyMaster provide source timestamps, JalinanDuta uses current time

3. **TelegramNotifier** - Sends formatted notifications
   - Only sends "We Sell" rates (customers buying foreign currency)
   - Uses HTML parse mode for formatting

### Data Flow

1. Bot fetches rates from 4 locations (Google Finance, 2x JalinanDuta, MyMoneyMaster)
2. Each source returns: `{'GBP': {'we_sell': X, 'we_buy': Y}, 'EUR': {...}, 'TRY': {...}}`
3. Rates saved to MySQL with location, currency, both rates, and timestamp
4. Telegram message formatted showing only "We Sell" rates from all sources
5. All activity logged to `exchange_rate_bot.log`

### Configuration

**my.json** (not in repo) - Required configuration file:
```json
{
  "telegram": {
    "bot_token": "...",
    "chat_id": "..."
  },
  "database": {
    "host": "localhost",
    "user": "remote",
    "password": "",
    "database": "exchange_rates",
    "socket": "/run/mysqld/mysqld.sock"
  }
}
```

Note: `exchange_rate_bot.py` uses absolute path `/home/remote/venv/cron/kl-exchange-rates/my.json` while `setup_database.py` uses relative path `my.json`

### Database Schema

**Table: exchange_rates**
- Stores both "We Sell" (green, higher) and "We Buy" (red, lower) rates
- Indexed on: location, currency, timestamp, and composite (location, currency, timestamp)
- we_sell_rate: Rate at which money changer sells foreign currency to customer
- we_buy_rate: Rate at which money changer buys foreign currency from customer

**View: latest_exchange_rates**
- Returns most recent rates for each location/currency combination
- Used for quick "current rate" queries

### Currency Support

Currently monitors: **GBP, EUR, TRY** (IDR was removed)

When adding/removing currencies:
1. Update URL constants (e.g., `GOOGLE_FINANCE_XXX_URL`)
2. Update `fetch_google_finance_rates()` currencies list
3. Update all `_parse_*()` methods to recognize currency codes
4. Update `format_rate_message()` to display the currency
5. Consider rate standardization (TRY is per 100, not per 1)

### Rate Standardization

- **GBP/EUR**: Used as-is (per 1 unit)
- **TRY**: Google Finance shows per 1 TRY, but we multiply by 100 to show "per 100 TRY" for consistency with money changers
- If adding currencies with different units, check both Google Finance and money changer conventions

## Deployment Notes

- Designed to run via cron (typical: twice daily at 9 AM and 5 PM)
- Uses virtual environment at `/opt/venv/venv/`
- Log files should not be committed (in .gitignore)
- Selenium is optional but recommended for sites with anti-bot protection
- Debug mode saves HTML files as `debug_*.html` when scraping fails

## Testing After Changes

After modifying currency support or parsing logic:
```bash
source /opt/venv/venv/bin/activate
python3 exchange_rate_bot.py
```

Verify:
1. All 4 sources successfully fetch rates (check logs)
2. Rates saved to database: `SELECT * FROM exchange_rates ORDER BY id DESC LIMIT 20;`
3. Telegram message sent with correct formatting
4. No IDR references remain if that was the change
