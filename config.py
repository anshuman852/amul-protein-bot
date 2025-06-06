import os

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

# Smart scheduling configuration
CHECK_INTERVAL_PEAK = int(os.getenv("CHECK_INTERVAL_PEAK", "120"))      # 2 minutes during peak hours (6am-4pm)
CHECK_INTERVAL_NORMAL = int(os.getenv("CHECK_INTERVAL_NORMAL", "600"))   # 10 minutes during normal hours (4pm-12am)
DOWNTIME_START_HOUR = int(os.getenv("DOWNTIME_START_HOUR", "0"))         # 12am (midnight)
DOWNTIME_END_HOUR = int(os.getenv("DOWNTIME_END_HOUR", "6"))             # 6am
PEAK_START_HOUR = int(os.getenv("PEAK_START_HOUR", "6"))                 # 6am
PEAK_END_HOUR = int(os.getenv("PEAK_END_HOUR", "16"))                    # 4pm

# Notification settings
NOTIFICATION_CHANNEL_ID = os.getenv("NOTIFICATION_CHANNEL_ID")           # Channel ID for stock notifications

# Legacy config for backward compatibility
CHECK_INTERVAL = CHECK_INTERVAL_PEAK  # Default to peak interval
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///app/data/amul_bot.db")

# API Endpoints
API_URL = "https://shop.amul.com/api/1/entity/ms.products?fields[name]=1&fields[brand]=1&fields[categories]=1&fields[collections]=1&fields[alias]=1&fields[sku]=1&fields[price]=1&fields[compare_price]=1&fields[original_price]=1&fields[images]=1&fields[metafields]=1&fields[discounts]=1&fields[catalog_only]=1&fields[is_catalog]=1&fields[seller]=1&fields[available]=1&fields[inventory_quantity]=1&fields[net_quantity]=1&fields[num_reviews]=1&fields[avg_rating]=1&fields[inventory_low_stock_quantity]=1&fields[inventory_allow_out_of_stock]=1&filters[0][field]=categories&filters[0][value][0]=protein&filters[0][operator]=in&facets=true&facetgroup=default_category_facet&limit=100&total=1&start=0"
HOMEPAGE_URL = "https://shop.amul.com/en/"
PREFERENCES_URL = "https://shop.amul.com/entity/ms.settings/_/setPreferences"

# Request headers
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "frontend": "1",
    "origin": "https://shop.amul.com",
    "priority": "u=1, i",
    "referer": "https://shop.amul.com/",
    "sec-ch-ua": '"Chromium";v="135", "Not-A.Brand";v="8"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
}

# Bot command descriptions
COMMANDS = {
    'start': 'Start the bot and get welcome message',
    'products': 'Browse and subscribe to products',
    'mysubs': 'View your subscribed products',
    'stock': 'Check current stock status of all products'
}

# Product Categories
PRODUCT_CATEGORIES = {
    'Whey Protein': {
        'emoji': '💪',
        'variants': {
            'Chocolate': [],
            'Unflavoured': []
        }
    },
    'Protein Shakes': {
        'emoji': '🥤',
        'variants': {
            'Chocolate': [],
            'Coffee': [],
            'Kesar': [],
            'Blueberry': []
        }
    },
    'Protein Drinks': {
        'emoji': '🥛',
        'variants': {
            'Milk': [],
            'Buttermilk': [],
            'Plain Lassi': [],
            'Rose Lassi': []
        }
    },
    'Paneer': {
        'emoji': '🧀',
        'variants': {
            'Regular': []
        }
    }
}
