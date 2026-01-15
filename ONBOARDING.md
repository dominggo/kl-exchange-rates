# Onboarding Guide - KL Exchange Rates Project

Welcome! This guide will help you quickly understand and continue development on this project.

## Project Overview

This is an exchange rate monitoring bot that:
- Scrapes exchange rates from multiple Malaysian money changers
- Supports GBP, EUR, IDR, and TRY to MYR conversions
- Sends notifications via Telegram
- Stores historical data in MySQL database
- Runs automatically via cron jobs

## Quick Start for Development

### 1. Project Structure

```
kl-exchange-rates/
├── exchange_rate_bot.py          # Main bot script
├── setup_database.py              # Database initialization
├── requirements.txt               # Python dependencies
├── my.json                        # Config file (not in repo - create this)
├── README.md                      # User documentation
├── EXCHANGE_RATE_BOT_README.md   # Detailed technical docs
├── ONBOARDING.md                  # This file
└── .gitignore                     # Git ignore rules
```

### 2. First Time Setup

```bash
# Clone and enter directory
cd P:\OneDrive\sync\project\03_exchange_rate

# Install dependencies
pip install -r requirements.txt

# Create your config file (if not exists)
# Copy structure from README.md section "Configure settings"
nano my.json

# Setup database
python3 setup_database.py

# Test run
python3 exchange_rate_bot.py
```

### 3. Key Configuration File: `my.json`

This file contains sensitive credentials (already in `.gitignore`):

```json
{
  "telegram": {
    "bot_token": "YOUR_BOT_TOKEN_FROM_BOTFATHER",
    "chat_id": "YOUR_CHAT_ID_FROM_USERINFOBOT"
  },
  "database": {
    "host": "localhost",
    "user": "remote",
    "password": "YOUR_DB_PASSWORD",
    "database": "exchange_rates",
    "socket": "/run/mysqld/mysqld.sock"
  }
}
```

## Current Data Sources

### 1. Google Finance
- **Currencies**: GBP, EUR, IDR, TRY
- **URLs**:
  - `https://www.google.com/finance/quote/GBP-MYR`
  - `https://www.google.com/finance/quote/EUR-MYR`
  - `https://www.google.com/finance/quote/IDR-MYR`
  - `https://www.google.com/finance/quote/TRY-MYR`
- **Rate Type**: Market rate (same for buy/sell)
- **Parser**: Extracts from HTML class `YMlKec fxKbKc`

### 2. JalinanDuta - Bukit Bintang
- **URL**: `https://www.jalinanduta.com/bukit-bintang/`
- **Currencies**: GBP, EUR, IDR, TRY
- **Rate Types**: Both We Buy and We Sell
- **Parser**: Table-based with CSS classes `table-green-color` and `table-red-color`

### 3. JalinanDuta - Masjid India
- **URL**: `https://www.jalinanduta.com/masjid-india/`
- **Currencies**: GBP, EUR, IDR, TRY
- **Rate Types**: Both We Buy and We Sell
- **Parser**: Same as Bukit Bintang

### 4. MyMoneyMaster
- **URL**: `http://www.mymoneymaster.com.my/Home/full_rate_board`
- **Currencies**: GBP, EUR, IDR, TRY
- **Rate Types**: Both We Buy and We Sell
- **Parser**: Rows with class `filtersearch`
- **Special**: Includes "Last Updated" timestamp from source

## Database Schema

### Table: `exchange_rates`

| Column | Type | Description |
|--------|------|-------------|
| id | INT | Primary key |
| location | VARCHAR(100) | Source name |
| currency | VARCHAR(10) | Currency code |
| we_sell_rate | DECIMAL(10,4) | Money changer sells to customer |
| we_buy_rate | DECIMAL(10,4) | Money changer buys from customer |
| timestamp | DATETIME | When rates were fetched |
| created_at | TIMESTAMP | Record creation time |

### View: `latest_exchange_rates`
Returns most recent rates for each location/currency pair.

## Common Development Tasks

### Adding a New Currency

1. Update source-specific parsers in `exchange_rate_bot.py`
2. Add currency code to lookup patterns
3. Test with manual run
4. Verify database storage

### Adding a New Data Source

1. Add URL constant at top of `exchange_rate_bot.py`
2. Create source-specific parser method (see existing `_parse_*` methods)
3. Add to `locations` list in `main()` function
4. Test scraping and parsing
5. Verify Telegram notification format

### Testing Changes

```bash
# Manual run with logs
python3 exchange_rate_bot.py

# Check logs
tail -f exchange_rate_bot.log

# Check database
mysql -u remote -p exchange_rates
SELECT * FROM latest_exchange_rates;

# Test specific parsing (add debug in code)
# The bot auto-saves debug_*.html files when scraping fails
```

### Understanding Rate Types

- **We Sell** (Green): Rate when YOU BUY foreign currency
- **We Buy** (Red): Rate when YOU SELL foreign currency
- **Telegram shows**: We Sell rates (what customers typically need)
- **Database stores**: Both rates for historical analysis

## Git Workflow

```bash
# Check current status
git status

# Stage changes
git add .

# Commit
git commit -m "Description of changes"

# Push
git push origin master

# Pull latest
git pull origin master
```

## Important Files (Not in Repo)

These files are auto-generated or contain secrets:
- `my.json` - Configuration with credentials
- `exchange_rate_bot.log` - Application logs
- `cron.log` - Cron execution logs
- `debug_*.html` - HTML dumps for debugging
- `__pycache__/` - Python cache
- `*.pyc` - Compiled Python files

## Useful Commands

```bash
# View recent application logs
tail -100 exchange_rate_bot.log

# View live logs
tail -f exchange_rate_bot.log

# Test database connection
python3 setup_database.py

# Query latest rates
mysql -u remote -p -e "SELECT * FROM exchange_rates.latest_exchange_rates;"

# Check cron jobs
crontab -l

# Edit cron jobs
crontab -e
```

## Troubleshooting Development Issues

### Issue: Module not found
```bash
pip install -r requirements.txt
```

### Issue: Database connection fails
```bash
# Check MySQL running
systemctl status mysql

# Test connection
mysql -u remote -p exchange_rates

# Recreate database
python3 setup_database.py
```

### Issue: Scraping fails (403 Forbidden)
- Bot has Selenium fallback built-in
- Check if Chrome/Chromium installed
- Review `debug_*.html` files
- Website may have changed structure

### Issue: No Telegram notifications
- Verify `bot_token` and `chat_id` in `my.json`
- Test bot manually: message your bot on Telegram first
- Check logs for error messages

## Future Development (Planned)

### Additional Data Sources to Integrate

1. **AntaraDuit**
   - URL: `https://www.antaraduit.com.my/exchange-rate.php`
   - Type: Comparison platform

2. **KL Money Changer**
   - EUR: `https://www.klmoneychanger.com/compare-rates?n=EUR`
   - GBP: `https://www.klmoneychanger.com/compare-rates?n=GBP`
   - Type: Rate comparison

3. **CashChanger**
   - GBP: `https://cashchanger.co/malaysia/gbp-to-myr`
   - EUR: `https://cashchanger.co/malaysia/eur-to-myr`
   - Type: Money changer aggregator

### Enhancement Ideas

- [ ] Add rate change alerts (notify when rate drops below threshold)
- [ ] Add historical rate charts
- [ ] Add rate comparison across all sources
- [ ] Add web dashboard for visualization
- [ ] Add support for more currencies (USD, SGD, AUD, etc.)
- [ ] Add rate trend analysis (7-day average, high/low)
- [ ] Add API endpoint for programmatic access
- [ ] Add export functionality (CSV, JSON)

## Key Code Sections

### Main Entry Point
File: `exchange_rate_bot.py`, Function: `main()`

### Source-Specific Parsers
- `_parse_google_finance()` - Google Finance parser
- `_parse_jalinanduta()` - JalinanDuta parser
- `_parse_mymoneymaster()` - MyMoneyMaster parser

### Data Flow
1. `fetch_html()` - HTTP request or Selenium fallback
2. `_parse_*()` - Extract rates from HTML
3. `save_to_database()` - Store in MySQL
4. `send_telegram()` - Send notification

### Telegram Formatting
File: `exchange_rate_bot.py`, Function: `format_rate_message()`

## Resources

- **Main Documentation**: README.md
- **Detailed Technical Docs**: EXCHANGE_RATE_BOT_README.md
- **GitHub Repo**: https://github.com/dominggo/kl-exchange-rates
- **Telegram Bot Setup**: @BotFather
- **Chat ID**: @userinfobot

## Getting Help

1. Check logs: `tail -100 exchange_rate_bot.log`
2. Review README.md troubleshooting section
3. Test components individually
4. Check debug HTML files if scraping fails
5. Verify database with direct MySQL queries

## Tips for Claude Code Terminal

When working in Claude Code terminal:

```bash
# Navigate to project
cd P:/OneDrive/sync/project/03_exchange_rate

# Common commands
python3 exchange_rate_bot.py          # Run bot
tail -f exchange_rate_bot.log         # Watch logs
git status                            # Check changes
git add . && git commit -m "msg"      # Quick commit
git push                              # Push changes

# Testing database
mysql -u remote -p exchange_rates -e "SELECT * FROM latest_exchange_rates;"
```

## Next Steps

1. Review the main `exchange_rate_bot.py` file
2. Test run the bot manually
3. Check Telegram notifications
4. Verify database is storing data
5. Consider adding one of the planned data sources
6. Set up cron job for automated runs

Happy coding! 🚀
