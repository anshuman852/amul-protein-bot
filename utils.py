from datetime import datetime, timedelta
import pytz
from models import Product
from config import PRODUCT_CATEGORIES, CHECK_INTERVAL_PEAK, CHECK_INTERVAL_NORMAL, DOWNTIME_START_HOUR, DOWNTIME_END_HOUR, PEAK_START_HOUR, PEAK_END_HOUR

# Always use Asia/Kolkata timezone for scheduling (Amul is Indian company)
IST = pytz.timezone('Asia/Kolkata')

def get_ist_time():
    """Get current time in IST timezone"""
    return datetime.now(IST)

def categorize_products(products):
    """Group products by category and variants"""
    # Create a deep copy to avoid shared references to variant lists
    categories = {}
    for category_name, category_data in PRODUCT_CATEGORIES.items():
        categories[category_name] = {
            'emoji': category_data['emoji'],
            'variants': {variant: [] for variant in category_data['variants']}
        }
    
    for product in products:
        name = product.name.lower()
        status = "🟢 In Stock" if product.available else "🔴 Out of Stock"
        price = f"₹{product.price}"
        
        # Extract pack info
        pack_info = ""
        if "pack of" in name:
            for part in name.split("|"):
                if "pack of" in part.lower():
                    pack_info = part.strip()
                    break
        
        # Add product link for in-stock items
        if product.available:
            product_link = f"https://shop.amul.com/product/{product.alias}"
            product_info = f"{status} - {pack_info} - {price} - <a href=\"{product_link}\">🛒 Shop</a>"
        else:
            product_info = f"{status} - {pack_info} - {price}"
        
        # Categorize product
        if "whey protein" in name:
            category = 'Whey Protein'
            variant = 'Chocolate' if 'chocolate' in name else 'Unflavoured'
        elif "milkshake" in name or "shake" in name:
            category = 'Protein Shakes'
            if 'chocolate' in name:
                variant = 'Chocolate'
            elif 'coffee' in name:
                variant = 'Coffee'
            elif 'blueberry' in name:
                variant = 'Blueberry'
            else:
                variant = 'Kesar'
        elif "paneer" in name:
            category = 'Paneer'
            variant = 'Regular'
        else:
            category = 'Protein Drinks'
            if 'milk' in name and 'shake' not in name:
                variant = 'Milk'
            elif 'buttermilk' in name:
                variant = 'Buttermilk'
            elif 'rose lassi' in name:
                variant = 'Rose Lassi'
            else:
                variant = 'Plain Lassi'
        
        categories[category]['variants'][variant].append(product_info)
    
    return categories

def format_notification_message(product):
    """Format notification message for product availability"""
    return f"""🎉 <b>Stock Update!</b>

<b>{product.name}</b>
📊 Status: <b>Now Available</b>
💰 Price: <b>₹{product.price}</b>
🏷️ SKU: <code>{product.sku}</code>

📍 You are receiving this notification because you subscribed to stock updates for this product.

🛒 <a href="https://shop.amul.com/product/{product.alias}">Shop now</a>

ℹ️ You will be notified again if this product goes out of stock and becomes available again."""

def format_stock_message(categories, last_check_time=None, check_interval=300):
    """Format stock status message with categories"""
    message = "📊 <b>Product Categories</b>\n\n"
    message += "🛒 <i>Click 'Shop' links to buy in-stock items</i>\n\n"
    
    for category_name, category_data in categories.items():
        has_products = False
        category_text = []
        
        # Add category header with bold formatting
        category_text.append(f"<b>{category_data['emoji']} {category_name}</b>\n")
        
        # Add variants with products
        for variant, products in category_data['variants'].items():
            if products:
                has_products = True
                category_text.append(f"<b>{variant}:</b>")
                category_text.extend(f"• {p}" for p in sorted(products))
                category_text.append("")  # Add empty line after each variant
        
        if has_products:
            message += "\n".join(category_text) + "\n"
    
    # Add timing information with better formatting
    message += "─" * 30 + "\n"
    if last_check_time:
        message += f"🕐 <b>Last updated:</b> {last_check_time.strftime('%Y-%m-%d %H:%M')}\n"
    
    # Show current schedule info
    schedule_info = get_schedule_info()
    message += f"📅 <b>Schedule:</b> {schedule_info}"
    
    return message

def create_product_from_api(api_product):
    """Create Product instance from API data"""
    return Product(
        id=api_product['_id'],
        name=api_product['name'],
        price=api_product['price'],
        sku=api_product['sku'],
        alias=api_product['alias'],
        available=api_product['available'] == 1
    )

def get_current_check_interval():
    """Get the appropriate check interval based on current IST time"""
    now = get_ist_time()
    current_hour = now.hour
    
    # Check if we're in downtime (12am - 6am IST)
    if DOWNTIME_START_HOUR <= current_hour < DOWNTIME_END_HOUR:
        return None  # No checking during downtime
    
    # Check if we're in peak hours (6am - 4pm IST)
    elif PEAK_START_HOUR <= current_hour < PEAK_END_HOUR:
        return CHECK_INTERVAL_PEAK  # 2 minutes
    
    # Normal hours (4pm - 12am IST)
    else:
        return CHECK_INTERVAL_NORMAL  # 10 minutes

def is_downtime():
    """Check if current IST time is within downtime hours"""
    current_hour = get_ist_time().hour
    return DOWNTIME_START_HOUR <= current_hour < DOWNTIME_END_HOUR

def get_next_active_time():
    """Get the next time when checking should resume (in IST)"""
    now = get_ist_time()
    
    if is_downtime():
        # If we're in downtime, next active time is at DOWNTIME_END_HOUR today
        next_active = now.replace(hour=DOWNTIME_END_HOUR, minute=0, second=0, microsecond=0)
        if next_active <= now:
            # If that time has passed, it's tomorrow
            next_active += timedelta(days=1)
        return next_active
    
    return now

def get_schedule_info():
    """Get human-readable schedule information"""
    current_interval = get_current_check_interval()
    now_ist = get_ist_time()
    
    if current_interval is None:
        next_active = get_next_active_time()
        return f"⏸️ Downtime (12am-6am IST) - Resuming at {next_active.strftime('%H:%M')} IST"
    elif current_interval == CHECK_INTERVAL_PEAK:
        return f"🚀 Peak hours (6am-4pm IST) - Checking every {current_interval//60} minutes"
    else:
        return f"🕐 Normal hours (4pm-12am IST) - Checking every {current_interval//60} minutes"
