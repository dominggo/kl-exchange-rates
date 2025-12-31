# KL Exchange Rates

A Python bot that monitors GBP and EUR to MYR exchange rates from Jalin & Duta money changers in Kuala Lumpur, sends notifications via Telegram, and stores historical data in MySQL.

## Features

- 📊 Scrapes both "We Sell" and "We Buy" rates for GBP→MYR and EUR→MYR
- 📍 Monitors rates from two locations: Bukit Bintang and Masjid India
- 📱 Sends formatted "We Sell" rate updates to Telegram
- 💾 Stores both rates in MySQL database with timestamps for historical tracking
- 📝 Comprehensive logging system with rotation
- ⏰ Designed for automated execution via cron jobs
- 🤖 Automatic fallback from HTTP requests to Selenium for anti-bot protection
- 🔍 Multiple parsing strategies to handle different HTML structures
- 🐛 Debug mode saves HTML for troubleshooting

## What are "We Sell" and "We Buy" rates?

- **We Sell** (Green column, higher rate): The rate at which the money changer **sells foreign currency to you**. Use this when you want to **buy GBP/EUR with MYR**.
- **We Buy** (Red column, lower rate): The rate at which the money changer **buys foreign currency from you**. Use this when you want to **sell GBP/EUR for MYR**.

The Telegram notification shows "We Sell" rates as these are typically what customers need when planning to buy foreign currency.

## Prerequisites

- Python 3.7+
- MySQL Server
- Telegram Bot Token (from @BotFather)
- Telegram Chat ID (from @userinfobot)
- Chrome/Chromium browser (optional, for Selenium fallback)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/dominggo/kl-exchange-rates.git
cd kl-exchange-rates
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Chrome/Chromium (Optional but Recommended)

The bot uses Selenium with Chrome as a fallback for JavaScript-heavy websites.

**Ubuntu/Debian:**
```bash
# Install Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f

# Or install Chromium
sudo apt-get install chromium-browser chromium-chromedriver
```

**Note:** The bot will first try simple HTTP requests. If that fails (403 error), it automatically falls back to Selenium with headless Chrome.

### 4. Configure settings

Create a `my.json` file with your credentials:

```json
{
  "telegram": {
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
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

**Required fields:**
- `telegram.bot_token`: Get from @BotFather on Telegram
- `telegram.chat_id`: Get from @userinfobot on Telegram

**Optional database fields** (defaults shown above)

### 5. Set up the database

Run the database setup script:

```bash
python3 setup_database.py
```

This will:
- Create the `exchange_rates` database
- Create the `exchange_rates` table with columns for both rates
- Create a `latest_exchange_rates` view

## How to Get Telegram Credentials

### Getting Bot Token

1. Open Telegram and search for **@BotFather**
2. Start a chat and send `/newbot`
3. Follow the prompts to create your bot
4. Copy the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Paste it in your `my.json` file as `bot_token`

### Getting Chat ID

1. Open Telegram and search for **@userinfobot**
2. Start a chat and send any message
3. The bot will reply with your user info including your Chat ID
4. Copy the Chat ID (a number like `123456789`)
5. Paste it in your `my.json` file as `chat_id`

**For Group Chats:**
1. Add your bot to the group
2. Send a message in the group
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Look for `"chat":{"id":` in the response (will be negative for groups)

## Usage

### Manual Execution

Run the bot manually:

```bash
python3 exchange_rate_bot.py
```

### Automated Execution with Cron

To run the bot twice daily (e.g., at 9 AM and 5 PM):

1. Open crontab:

```bash
crontab -e
```

2. Add the following lines:

```bash
# Exchange Rate Bot - Runs at 9 AM and 5 PM daily
0 9 * * * cd /path/to/kl-exchange-rates && python3 exchange_rate_bot.py >> cron.log 2>&1
0 17 * * * cd /path/to/kl-exchange-rates && python3 exchange_rate_bot.py >> cron.log 2>&1
```

**Note:** Replace `/path/to/kl-exchange-rates` with your actual project directory.

### Alternative Cron Schedule Examples

```bash
# Every 6 hours
0 */6 * * * cd /path/to/kl-exchange-rates && python3 exchange_rate_bot.py

# Every day at 10 AM
0 10 * * * cd /path/to/kl-exchange-rates && python3 exchange_rate_bot.py

# Twice daily at 8 AM and 8 PM
0 8,20 * * * cd /path/to/kl-exchange-rates && python3 exchange_rate_bot.py

# Every weekday at 9 AM
0 9 * * 1-5 cd /path/to/kl-exchange-rates && python3 exchange_rate_bot.py
```

## Database Schema

### Table: exchange_rates

| Column | Type | Description |
|--------|------|-------------|
| id | INT | Auto-increment primary key |
| location | VARCHAR(100) | Money changer location (Bukit Bintang, Masjid India) |
| currency | VARCHAR(10) | Currency code (GBP, EUR) |
| we_sell_rate | DECIMAL(10,4) | "We Sell" rate (money changer sells to customer) |
| we_buy_rate | DECIMAL(10,4) | "We Buy" rate (money changer buys from customer) |
| timestamp | DATETIME | When the rates were fetched |
| created_at | TIMESTAMP | When the record was created |

**Indexes:**
- `idx_location` - Fast lookup by location
- `idx_currency` - Fast lookup by currency
- `idx_timestamp` - Fast lookup by time
- `idx_location_currency_timestamp` - Fast lookup for latest rates

### View: latest_exchange_rates

Returns the most recent rates for each location and currency combination.

## Querying the Database

### Get latest rates

```sql
SELECT * FROM latest_exchange_rates;
```

### Get all rates for today

```sql
SELECT *
FROM exchange_rates
WHERE DATE(timestamp) = CURDATE()
ORDER BY timestamp DESC;
```

### Get GBP rate history for Bukit Bintang

```sql
SELECT we_sell_rate, we_buy_rate, timestamp
FROM exchange_rates
WHERE location = 'Bukit Bintang'
  AND currency = 'GBP'
ORDER BY timestamp DESC
LIMIT 10;
```

### Compare rates between locations

```sql
SELECT
    location,
    currency,
    we_sell_rate,
    we_buy_rate,
    timestamp
FROM latest_exchange_rates
ORDER BY currency, location;
```

### Calculate average rates for the last 30 days

```sql
SELECT
    location,
    currency,
    AVG(we_sell_rate) as avg_sell_rate,
    AVG(we_buy_rate) as avg_buy_rate,
    MIN(we_sell_rate) as min_sell_rate,
    MAX(we_sell_rate) as max_sell_rate,
    COUNT(*) as sample_count
FROM exchange_rates
WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY location, currency;
```

### Track rate spread (difference between buy and sell)

```sql
SELECT
    location,
    currency,
    we_sell_rate,
    we_buy_rate,
    (we_sell_rate - we_buy_rate) as spread,
    ROUND(((we_sell_rate - we_buy_rate) / we_sell_rate * 100), 2) as spread_percent,
    timestamp
FROM latest_exchange_rates
ORDER BY currency, location;
```

## Logs

The bot creates two types of logs:

1. **Application Log**: `exchange_rate_bot.log` - Detailed execution logs
2. **Cron Log**: `cron.log` - Output from cron job execution (if configured)

View recent logs:

```bash
tail -f exchange_rate_bot.log
```

## Troubleshooting

### Bot doesn't send messages to Telegram

- Verify `telegram.bot_token` is correct in `my.json`
- Verify `telegram.chat_id` is correct in `my.json`
- Make sure you've started a chat with your bot first
- Check the logs for error messages: `tail -100 exchange_rate_bot.log`

### Database connection fails

- Ensure MySQL is running: `systemctl status mysql`
- Verify database credentials in `my.json`
- Check if socket path exists: `ls -l /run/mysqld/mysqld.sock`
- Try connecting manually: `mysql -u remote -p exchange_rates`

### No rates fetched

- Check if the websites are accessible: `curl -I https://www.jalinanduta.com/masjid-india/`
- The bot automatically tries multiple methods:
  1. Simple HTTP request
  2. Selenium with headless Chrome (if request fails)
  3. Multiple parsing strategies (tables, divs, text search)
- Check `exchange_rate_bot.log` for specific errors
- Look for `debug_*.html` files - these contain the fetched HTML for inspection
- If the HTML structure changed, you may need to update the `_parse_rates()` method
- Ensure Selenium and Chrome are installed if you see "403 Forbidden" errors

### Selenium/Chrome issues

- **Selenium not found**: `pip install selenium`
- **ChromeDriver not found**:
  ```bash
  # Ubuntu/Debian
  sudo apt-get install chromium-chromedriver
  # Or download from https://chromedriver.chromium.org/
  ```
- **Chrome binary not found**: `sudo apt-get install google-chrome-stable`
- Check Selenium is working: `python3 -c "from selenium import webdriver; print('OK')"`

### Cron job not running

- Check cron service: `systemctl status cron`
- Verify crontab entry: `crontab -l`
- Check cron log: `grep CRON /var/log/syslog`
- Ensure full paths are used in crontab
- Check file permissions: `ls -l exchange_rate_bot.py`

## Customization

### Adding more currencies

Edit `exchange_rate_bot.py` and update the `_parse_rates()` method to recognize additional currencies (e.g., USD, SGD).

### Changing message format

Modify the `format_rate_message()` function in `exchange_rate_bot.py`. You can choose to display both rates or just one.

### Adding more locations

Add new URL and location tuples to the `locations` list in the `main()` function:

```python
locations = [
    (BUKIT_BINTANG_URL, "Bukit Bintang"),
    (MASJID_INDIA_URL, "Masjid India"),
    ("https://example.com/location3", "Location 3")
]
```

## Files

- `exchange_rate_bot.py` - Main bot script
- `setup_database.py` - Database setup script
- `requirements.txt` - Python dependencies
- `my.json` - Configuration file (create this, not in repo)
- `README.md` - This file
- `exchange_rate_bot.log` - Application logs (auto-generated)
- `debug_*.html` - Debug HTML files (auto-generated when scraping fails)

## Security Notes

- Never commit `my.json` to version control (already in `.gitignore`)
- Keep your Telegram bot token secure
- Restrict MySQL user permissions to only the `exchange_rates` database
- Set proper file permissions: `chmod 600 my.json`

## Architecture

### How the Bot Works

1. **Scraping**: Fetches HTML from Jalin & Duta money changer websites
2. **Parsing**: Extracts both "We Sell" (green) and "We Buy" (red) rates from table cells
3. **Storage**: Saves both rates to MySQL with timestamp and location
4. **Notification**: Formats and sends "We Sell" rates to Telegram
5. **Logging**: Records all activities for monitoring and debugging

### Rate Detection

The bot identifies rates by:
- Looking for the currency code (GBP, EUR) in table columns
- Finding cells with CSS class `table-green-color` (We Sell) and `table-red-color` (We Buy)
- Fallback strategies if CSS classes are not found

## Support

For issues or questions:
1. Check the logs: `tail -100 exchange_rate_bot.log`
2. Verify configuration in `my.json`
3. Test database connection: `python3 setup_database.py`
4. Test manual execution: `python3 exchange_rate_bot.py`
5. Check debug HTML files if scraping fails

## License

This project is provided as-is for personal use.
