from datetime import datetime, timedelta
from models import Product
from config import PRODUCT_CATEGORIES

def categorize_products(products):
    """Group products by category and variants"""
    categories = PRODUCT_CATEGORIES.copy()
    
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
    
    next_check = datetime.now() + timedelta(seconds=check_interval)
    message += f"⏰ <b>Next check in:</b> {check_interval//60} minutes (around {next_check.strftime('%H:%M')})"
    
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