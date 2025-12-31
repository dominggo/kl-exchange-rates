# KL Exchange Rates

A Python bot that monitors exchange rates from Malaysian money changers and sends notifications via Telegram.

## Features

- Fetches GBP and EUR to MYR exchange rates from Jalin & Duta money changers
- Monitors rates from multiple locations (Bukit Bintang and Masjid India)
- Sends formatted updates to Telegram
- Stores historical data in MySQL database
- Automatic fallback from HTTP requests to Selenium for anti-bot protection
- Multiple parsing strategies to handle different HTML structures
- Comprehensive logging system
- Designed for automated execution via cron jobs

## Prerequisites

- Python 3.7+
- MySQL Server
- Telegram Bot Token (from @BotFather)
- Telegram Chat ID (from @userinfobot)
- Chrome/Chromium browser (optional, for Selenium fallback)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/dominggo/kl-exchange-rates.git
cd kl-exchange-rates
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Configure settings:
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

4. Set up the database:
```bash
python3 setup_database.py
```

## Usage

### Manual Execution
```bash
python3 exchange_rate_bot.py
```

### Automated Execution with Cron
Run the bot twice daily (9 AM and 5 PM):
```bash
crontab -e
```

Add:
```bash
0 9 * * * cd /path/to/kl-exchange-rates && python3 exchange_rate_bot.py >> cron.log 2>&1
0 17 * * * cd /path/to/kl-exchange-rates && python3 exchange_rate_bot.py >> cron.log 2>&1
```

## Database Schema

The bot stores exchange rates in MySQL with the following structure:

### Table: exchange_rates
- `id` - Auto-increment primary key
- `location` - Money changer location
- `currency` - Currency code (GBP, EUR)
- `rate` - Exchange rate
- `timestamp` - When the rate was fetched
- `created_at` - Record creation timestamp

### View: latest_exchange_rates
Returns the most recent rate for each location and currency combination.

## Troubleshooting

- **No Telegram messages**: Verify bot token and chat ID in `my.json`
- **Database connection fails**: Check MySQL is running and credentials are correct
- **No rates fetched**: Check website accessibility and review logs in `exchange_rate_bot.log`
- **Selenium issues**: Install Chrome/Chromium and chromedriver

## Security

- Never commit `my.json` to version control
- Keep your Telegram bot token secure
- Restrict MySQL user permissions appropriately
- Set proper file permissions: `chmod 600 my.json`

## Files

- `exchange_rate_bot.py` - Main bot script
- `requirements.txt` - Python dependencies
- `EXCHANGE_RATE_BOT_README.md` - Detailed documentation
- `my.json` - Configuration file (not included in repo)

## Documentation

For detailed documentation, see [EXCHANGE_RATE_BOT_README.md](EXCHANGE_RATE_BOT_README.md)

## License

This project is provided as-is for personal use.
