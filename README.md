# Amul Stock Monitor Bot

A Telegram bot to monitor stock status of Amul protein products and send notifications when items become available.

## Features

- Monitor product availability in real-time
- Subscribe to product stock notifications
- View products by categories
- Track subscription history
- Get instant stock status updates

## Project Structure

```
amul-bot/
├── api.py           # API communication logic
├── bot.py           # Main bot application
├── config.py        # Configuration and constants
├── handlers.py      # Telegram command handlers
├── models.py        # Database models
├── utils.py         # Helper functions
├── requirements.txt # Python dependencies
└── .env            # Environment variables
```

## Setup

1. Clone the repository:
```bash
git clone [repository-url]
cd amul-bot
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env and add your bot token from @BotFather
```

5. Start the bot:
```bash
python bot.py
```

## Bot Commands

- `/start` - Start the bot and get welcome message
- `/products` - Browse and subscribe to products
- `/mysubs` - View your subscribed products
- `/stock` - Check current stock status of all products

## Docker Deployment

### Using Pre-built Images (Recommended)

Multi-architecture Docker images are automatically built and published to GitHub Container Registry (GHCR) for both `amd64` and `arm64` platforms.

1. Pull and run the latest image:
```bash
docker run -d \
  --name amul-bot \
  -e BOT_TOKEN=your_bot_token_here \
  -v $(pwd)/data:/app/data \
  ghcr.io/your-username/amul-bot:latest
```

2. Or use docker-compose with the pre-built image:
```yaml
version: '3.8'
services:
  amul-bot:
    image: ghcr.io/your-username/amul-bot:latest
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

### Building Locally

1. Build and start:
```bash
docker-compose up -d
```

2. Check logs:
```bash
docker-compose logs -f
```

3. Stop:
```bash
docker-compose down
```

## Available Docker Tags

- `latest` - Latest stable release from main branch
- `develop` - Latest development build
- `v1.0.0` - Specific version tags
- All tags support both `linux/amd64` and `linux/arm64` architectures

## Database

The bot uses SQLite database stored in the `data/` directory. The database is automatically created on first run with all necessary tables.

## Product Categories

Products are organized into the following categories:

1. 💪 Whey Protein
   - Chocolate
   - Unflavoured

2. 🥤 Protein Shakes
   - Chocolate
   - Coffee
   - Kesar
   - Blueberry

3. 🥛 Protein Drinks
   - Milk
   - Buttermilk
   - Plain Lassi
   - Rose Lassi

4. 🧀 Paneer
   - Regular

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.