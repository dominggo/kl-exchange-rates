# Exchange Rate Telegram Bot

A Python bot that fetches GBP and EUR to MYR exchange rates from Jalin & Duta money changers, posts them to Telegram, and stores the data in a MySQL database.

## Features

- 📊 Scrapes "We Sell" rates for GBP→MYR and EUR→MYR
- 📍 Fetches from two locations: Bukit Bintang and Masjid India
- 📱 Sends formatted updates to Telegram
- 💾 Records all rates in MySQL database with timestamps
- 📝 Comprehensive logging
- ⏰ Designed for cron job execution (twice daily)
- 🤖 Automatic fallback from HTTP requests to Selenium for anti-bot protection
- 🔍 Multiple parsing strategies to handle different HTML structures
- 🐛 Debug mode saves HTML for troubleshooting

## Prerequisites

- Python 3.7+
- MySQL Server
- Telegram Bot Token (from @BotFather)
- Your Telegram Chat ID (from @userinfobot)
- Chrome/Chromium browser (optional, for Selenium fallback)

## Installation

### 1. Clone or navigate to the project directory

```bash
cd /home/user/sequal
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2a. Install Chrome/Chromium (Optional but Recommended)

The bot uses Selenium with Chrome as a fallback for JavaScript-heavy websites. Install Chrome or Chromium:

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

### 3. Configure settings

Copy the example configuration file and edit it:

```bash
cp my.json.example my.json
nano my.json
```

Edit the following values in `my.json`:

```json
{
  "telegram": {
    "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
    "chat_id": "123456789"
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

### 4. Set up the database

Run the database setup script:

```bash
python3 setup_database.py
```

This will:
- Create the `exchange_rates` database
- Create the `exchange_rates` table
- Create a `latest_exchange_rates` view

### 5. Make the script executable

```bash
chmod +x exchange_rate_bot.py
```

## Usage

### Manual Execution

Run the bot manually:

```bash
python3 exchange_rate_bot.py
```

Or:

```bash
./exchange_rate_bot.py
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
0 9 * * * cd /home/user/sequal && /usr/bin/python3 /home/user/sequal/exchange_rate_bot.py >> /home/user/sequal/cron.log 2>&1
0 17 * * * cd /home/user/sequal && /usr/bin/python3 /home/user/sequal/exchange_rate_bot.py >> /home/user/sequal/cron.log 2>&1
```

**Note:** Adjust the paths if your Python installation or project directory is different.

### Alternative Cron Schedule Examples

```bash
# Every 6 hours
0 */6 * * * cd /home/user/sequal && python3 exchange_rate_bot.py

# Every day at 10 AM
0 10 * * * cd /home/user/sequal && python3 exchange_rate_bot.py

# Twice daily at 8 AM and 8 PM
0 8,20 * * * cd /home/user/sequal && python3 exchange_rate_bot.py

# Every weekday at 9 AM
0 9 * * 1-5 cd /home/user/sequal && python3 exchange_rate_bot.py
```

## How to Get Telegram Credentials

### Getting Bot Token

1. Open Telegram and search for **@BotFather**
2. Start a chat and send `/newbot`
3. Follow the prompts to create your bot
4. Copy the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Paste it in your `.env` file as `TELEGRAM_BOT_TOKEN`

### Getting Chat ID

1. Open Telegram and search for **@userinfobot**
2. Start a chat and send any message
3. The bot will reply with your user info including your Chat ID
4. Copy the Chat ID (a number like `123456789`)
5. Paste it in your `.env` file as `TELEGRAM_CHAT_ID`

**For Group Chats:**
1. Add your bot to the group
2. Send a message in the group
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Look for `"chat":{"id":` in the response (will be negative for groups)

## Database Schema

### Table: exchange_rates

| Column | Type | Description |
|--------|------|-------------|
| id | INT | Auto-increment primary key |
| location | VARCHAR(100) | Money changer location |
| currency | VARCHAR(10) | Currency code (GBP, EUR) |
| rate | DECIMAL(10,4) | Exchange rate |
| timestamp | DATETIME | When the rate was fetched |
| created_at | TIMESTAMP | When the record was created |

### View: latest_exchange_rates

Returns the most recent rate for each location and currency combination.

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
SELECT rate, timestamp
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
    rate,
    timestamp
FROM latest_exchange_rates
ORDER BY currency, location;
```

### Calculate average rate for the last 30 days

```sql
SELECT
    location,
    currency,
    AVG(rate) as avg_rate,
    MIN(rate) as min_rate,
    MAX(rate) as max_rate,
    COUNT(*) as sample_count
FROM exchange_rates
WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY location, currency;
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
- Check the logs for error messages

### Database connection fails

- Ensure MySQL is running: `systemctl status mysql`
- Verify database credentials in `my.json`
- Check if socket path exists: `ls -l /run/mysqld/mysqld.sock`
- Try connecting manually: `mysql -u remote`

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

Edit `exchange_rate_bot.py` and update the `_parse_rates()` method to recognize additional currencies.

### Changing message format

Modify the `format_rate_message()` function in `exchange_rate_bot.py`.

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
- `my.json` - Configuration file (create from `my.json.example`)
- `my.json.example` - Example configuration
- `exchange_rate_bot.log` - Application logs
- `EXCHANGE_RATE_BOT_README.md` - This file

## Security Notes

- Never commit `my.json` file to version control
- Keep your Telegram bot token secure
- The `my.json` file contains sensitive credentials
- Restrict MySQL user permissions to only the `exchange_rates` database
- Ensure `my.json` has appropriate file permissions (e.g., `chmod 600 my.json`)

## License

This script is provided as-is for personal use.

## Support

For issues or questions:
1. Check the logs: `tail -100 exchange_rate_bot.log`
2. Verify configuration in `my.json`
3. Test database connection: `python3 setup_database.py`
4. Test manual execution: `python3 exchange_rate_bot.py`
