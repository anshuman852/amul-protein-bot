import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models import Product, User, Subscription
from config import CHECK_INTERVAL
from utils import categorize_products, format_notification_message, format_stock_message, create_product_from_api
from api import get_products

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Send welcome message and store user"""
    user_id = str(update.effective_user.id)
    
    # Create user if not exists
    user_query = select(User).where(User.id == user_id)
    user = await session.scalar(user_query)
    if not user:
        user = User(id=user_id)
        session.add(user)
        await session.commit()
        logger.info(f"New user registered: {user_id}")
    
    welcome_msg = """Welcome! I'll help you track Amul protein products.

Use /products to see available products and subscribe to stock notifications.

📝 For any suggestions or feedback, please contact @anshuman852"""
    await update.message.reply_text(welcome_msg)

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Show product categories"""
    try:
        # First try to get products from database
        products_query = select(Product).options(
            selectinload(Product.subscriptions)
        )
        result = await session.execute(products_query)
        products = result.scalars().all()
        
        # If no products in database, fetch from API and save
        if not products:
            logger.info("No products in database, fetching from API...")
            api_products = await get_products()
            products = []
            
            if not api_products:
                await update.message.reply_text(
                    "Unable to fetch products at the moment. Please try again later."
                )
                return
            
            for api_product in api_products:
                product = create_product_from_api(api_product)
                session.add(product)
                products.append(product)
            
            await session.commit()
            logger.info(f"Added {len(products)} products to database")
        
        # Categorize products to get counts
        categories = categorize_products(products)
        
        # Create keyboard with category buttons
        keyboard = []
        for category_name, category_data in categories.items():
            # Count available and total products in category
            total_products = sum(len(variants) for variants in category_data['variants'].values())
            available_count = 0
            for variants in category_data['variants'].values():
                for product_info in variants:
                    if "🟢 In Stock" in product_info:
                        available_count += 1
            
            if total_products > 0:  # Only show categories that have products
                status_icon = "🟢" if available_count > 0 else "🔴"
                button = InlineKeyboardButton(
                    f"{category_data['emoji']} {category_name} {status_icon} ({available_count}/{total_products})",
                    callback_data=f"category_{category_name.replace(' ', '_')}"
                )
                keyboard.append([button])
        
        if keyboard:
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🛒 <b>Product Categories</b>\n\n"
                "📱 Select a category to view products and subscribe\n"
                "🟢 = Has available items | 🔴 = All out of stock\n"
                "Numbers show (available/total) products",
                reply_markup=reply_markup,
                parse_mode=constants.ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                "No products available at the moment. Please try again later."
            )
            
    except Exception as e:
        logger.error(f"Error in list_products: {e}")
        await update.message.reply_text(
            "An error occurred while fetching products. Please try again later."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Handle button presses for categories and product subscriptions"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # Handle category selection
    if query.data.startswith("category_"):
        category_name = query.data.replace("category_", "").replace("_", " ")
        await show_category_products(query, context, session, category_name)
        return
    
    # Handle back to categories
    if query.data == "back_to_categories":
        await show_categories_again(query, context, session)
        return
    
    # Handle product subscription toggle
    if query.data.startswith("toggle_"):
        product_id = query.data.replace("toggle_", "")
        
        # Get current product status
        product_query = select(Product).where(Product.id == product_id)
        product = await session.scalar(product_query)
        
        if not product:
            await query.edit_message_text("Error: Product not found.")
            return
        
        # Check existing subscription
        sub_query = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.product_id == product_id
        )
        subscription = await session.scalar(sub_query)
        
        if subscription:
            # Unsubscribe
            await session.delete(subscription)
            message = f"❌ <b>Unsubscribed from:</b>\n{product.name}\n\n📵 You won't receive notifications for this product anymore."
            logger.info(f"User {user_id} unsubscribed from product {product_id}")
        else:
            # Subscribe with current stock status
            subscription = Subscription(
                user_id=user_id,
                product_id=product_id,
                last_stock_status=product.available,
                notified=product.available  # If product is available, mark as notified
            )
            session.add(subscription)
            
            status = "🟢 in stock" if product.available else "🔴 out of stock"
            message = f"""✅ <b>Subscribed to:</b>
{product.name}

📊 <b>Current Status:</b> {status}
💰 <b>Price:</b> ₹{product.price}

🔔 <b>You will be notified when:</b>
• Product comes back in stock (if currently unavailable)
• Product becomes unavailable (if currently in stock)"""
            logger.info(f"User {user_id} subscribed to product {product_id}")
        
        await session.commit()
        await query.edit_message_text(text=message, parse_mode=constants.ParseMode.HTML)

async def show_category_products(query, context: ContextTypes.DEFAULT_TYPE, session, category_name: str):
    """Show products in a specific category"""
    try:
        user_id = str(query.from_user.id)
        
        # Get all products
        products_query = select(Product).options(
            selectinload(Product.subscriptions)
        )
        result = await session.execute(products_query)
        products = result.scalars().all()
        
        # Categorize products
        categories = categorize_products(products)
        
        if category_name not in categories:
            await query.edit_message_text("Category not found.")
            return
        
        category_data = categories[category_name]
        
        # Build product list with numbers
        message = f"{category_data['emoji']} <b>{category_name}</b>\n\n"
        
        # Store products for number selection
        category_products = []
        product_number = 1
        
        for variant_name, variant_products in category_data['variants'].items():
            if variant_products:
                message += f"<b>{variant_name}:</b>\n"
                
                for product_info in sorted(variant_products):
                    # Extract product details from the formatted string
                    # Format: "🟢 In Stock - pack of X - ₹YYYY - 🛒 Shop"
                    parts = product_info.split(" - ")
                    status_icon = "🟢" if "🟢 In Stock" in product_info else "🔴"
                    
                    # Find the actual product object
                    matching_product = None
                    for product in products:
                        if f"₹{product.price}" in product_info:
                            # Additional matching logic based on pack info
                            name_lower = product.name.lower()
                            if variant_name.lower() in name_lower or category_name.lower() in name_lower:
                                matching_product = product
                                break
                    
                    if matching_product:
                        # Check if user is subscribed
                        is_subscribed = any(sub.user_id == user_id and not sub.notified 
                                          for sub in matching_product.subscriptions)
                        sub_icon = " ✅" if is_subscribed else ""
                        
                        # Add product link for in-stock items
                        shop_link = ""
                        if matching_product.available:
                            shop_link = f" - <a href=\"https://shop.amul.com/product/{matching_product.alias}\">🛒 Shop</a>"
                        
                        message += f"{product_number}. {status_icon} {parts[1]} - ₹{matching_product.price}{sub_icon}{shop_link}\n"
                        category_products.append(matching_product)
                        product_number += 1
                
                message += "\n"
        
        # Store category products in context for number commands
        context.user_data['category_products'] = category_products
        context.user_data['category_name'] = category_name
        
        message += "─" * 30 + "\n"
        message += "📱 <b>How to subscribe:</b>\n"
        message += "• Use buttons below for quick actions\n"
        message += "• Or send /&lt;number&gt; (e.g., /1, /2) to subscribe\n"
        message += "• Send /&lt;number&gt; again to unsubscribe\n\n"
        message += f"🟢 = In Stock | 🔴 = Out of Stock | ✅ = Subscribed"
        
        # Create keyboard with quick action buttons
        keyboard = []
        
        # Add "Back to Categories" button
        keyboard.append([InlineKeyboardButton("⬅️ Back to Categories", callback_data="back_to_categories")])
        
        # Add individual product buttons for all products (2 per row)
        for i in range(0, len(category_products), 2):
            row = []
            for j in range(2):
                if i + j < len(category_products):
                    product = category_products[i + j]
                    is_subscribed = any(sub.user_id == user_id and not sub.notified 
                                      for sub in product.subscriptions)
                    button_text = f"{'✅' if is_subscribed else '📝'} {i+j+1}"
                    row.append(InlineKeyboardButton(button_text, callback_data=f"toggle_{product.id}"))
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=constants.ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error showing category products: {e}")
        await query.edit_message_text("An error occurred. Please try again.")

async def my_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Show user's subscribed products with detailed status"""
    user_id = str(update.effective_user.id)
    
    # Get all user's subscriptions with products
    subs_query = select(Subscription).where(
        Subscription.user_id == user_id
    ).options(selectinload(Subscription.product))
    
    result = await session.execute(subs_query)
    subscriptions = result.scalars().all()
    
    if not subscriptions:
        await update.message.reply_text(
            "You haven't subscribed to any products yet.\n"
            "Use /products to browse and subscribe to products."
        )
        return
    
    # Group subscriptions by notification status
    waiting_for_stock = []
    waiting_for_restock = []  # Products that were in stock but went out
    currently_in_stock = []
    
    for sub in subscriptions:
        product = sub.product
        status = "🟢 In Stock" if product.available else "🔴 Out of Stock"
        price = f"₹{product.price}"
        
        subscription_info = f"• {product.name} - {price}\n  Status: {status}"
        
        # Add shop link for in-stock products
        if product.available:
            product_link = f"https://shop.amul.com/product/{product.alias}"
            subscription_info += f"\n  🛒 <a href=\"{product_link}\">Shop now</a>"
        
        if sub.last_notified_at:
            subscription_info += f"\n  Last notification: {sub.last_notified_at.strftime('%Y-%m-%d %H:%M')}"
        
        if product.available:
            currently_in_stock.append(subscription_info)
        elif sub.last_notified_at:
            waiting_for_restock.append(subscription_info)  # Was in stock before
        else:
            waiting_for_stock.append(subscription_info)  # Never been in stock
    
    message = "📬 <b>Your Subscriptions</b>\n\n"
    
    if waiting_for_stock:
        message += "<b>🔄 Waiting for Stock:</b>\n" + "\n\n".join(waiting_for_stock) + "\n\n"
    
    if waiting_for_restock:
        message += "<b>⏳ Waiting for Restock:</b>\n" + "\n\n".join(waiting_for_restock) + "\n\n"
        
    if currently_in_stock:
        message += "<b>✅ Currently Available:</b>\n" + "\n\n".join(currently_in_stock) + "\n\n"
    
    message += "─" * 30 + "\n"
    message += "ℹ️ You will be notified when products come back in stock.\n"
    message += "📱 Use /products to manage your subscriptions."
    
    await update.message.reply_text(message, parse_mode=constants.ParseMode.HTML)

async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Show current stock status of all products"""
    try:
        # Get all products ordered by name
        products_query = select(Product).order_by(Product.name)
        result = await session.execute(products_query)
        products = result.scalars().all()
        
        if not products:
            await update.message.reply_text(
                "No products found in database. Please try again later."
            )
            return
        
        # Get last update time
        last_check_time = max((p.last_checked for p in products if p.last_checked), default=None)
        
        # Categorize and format message
        categories = categorize_products(products)
        message = format_stock_message(categories, last_check_time, CHECK_INTERVAL)
        
        await update.message.reply_text(message, parse_mode=constants.ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error in stock command: {e}")
        await update.message.reply_text(
            "An error occurred while fetching stock status. Please try again later."
        )

async def show_categories_again(query, context: ContextTypes.DEFAULT_TYPE, session):
    """Show product categories again"""
    try:
        # Get all products
        products_query = select(Product).options(
            selectinload(Product.subscriptions)
        )
        result = await session.execute(products_query)
        products = result.scalars().all()
        
        # Categorize products to get counts
        categories = categorize_products(products)
        
        # Create keyboard with category buttons
        keyboard = []
        for category_name, category_data in categories.items():
            # Count available and total products in category
            total_products = sum(len(variants) for variants in category_data['variants'].values())
            available_count = 0
            for variants in category_data['variants'].values():
                for product_info in variants:
                    if "🟢 In Stock" in product_info:
                        available_count += 1
            
            if total_products > 0:  # Only show categories that have products
                status_icon = "🟢" if available_count > 0 else "🔴"
                button = InlineKeyboardButton(
                    f"{category_data['emoji']} {category_name} {status_icon} ({available_count}/{total_products})",
                    callback_data=f"category_{category_name.replace(' ', '_')}"
                )
                keyboard.append([button])
        
        if keyboard:
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🛒 <b>Product Categories</b>\n\n"
                "📱 Select a category to view products and subscribe\n"
                "🟢 = Has available items | 🔴 = All out of stock\n"
                "Numbers show (available/total) products",
                reply_markup=reply_markup,
                parse_mode=constants.ParseMode.HTML
            )
        else:
            await query.edit_message_text("No products available at the moment. Please try again later.")
            
    except Exception as e:
        logger.error(f"Error showing categories: {e}")
        await query.edit_message_text("An error occurred. Please try again.")

async def handle_number_command(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Handle /1, /2, etc. commands for product subscription"""
    try:
        # Extract number from command
        command_text = update.message.text.strip()
        if not command_text.startswith('/') or len(command_text) < 2:
            return
        
        try:
            number = int(command_text[1:])  # Remove the '/' and convert to int
        except ValueError:
            return  # Not a valid number command
        
        user_id = str(update.effective_user.id)
        
        # Check if user has category products stored
        if not context.user_data or 'category_products' not in context.user_data:
            await update.message.reply_text(
                "Please first select a category using /products command."
            )
            return
        
        category_products = context.user_data.get('category_products', [])
        category_name = context.user_data.get('category_name', 'Unknown')
        
        # Check if number is valid
        if number < 1 or number > len(category_products):
            await update.message.reply_text(
                f"Invalid number. Please choose between 1 and {len(category_products)}."
            )
            return
        
        # Get the product (convert to 0-based index)
        product = category_products[number - 1]
        
        # Check existing subscription
        sub_query = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.product_id == product.id
        )
        subscription = await session.scalar(sub_query)
        
        if subscription:
            # Unsubscribe
            await session.delete(subscription)
            message = f"❌ <b>Unsubscribed from:</b>\n{product.name}\n\n📵 You won't receive notifications for this product anymore."
            logger.info(f"User {user_id} unsubscribed from product {product.id} via /{number}")
        else:
            # Subscribe
            subscription = Subscription(
                user_id=user_id,
                product_id=product.id,
                last_stock_status=product.available,
                notified=product.available
            )
            session.add(subscription)
            
            status = "🟢 in stock" if product.available else "🔴 out of stock"
            shop_link = ""
            if product.available:
                shop_link = f"\n\n🛒 <a href=\"https://shop.amul.com/product/{product.alias}\">Shop now</a>"
            
            message = f"""✅ <b>Subscribed to:</b>
{product.name}

📊 <b>Current Status:</b> {status}
💰 <b>Price:</b> ₹{product.price}

🔔 <b>You will be notified when:</b>
• Product comes back in stock (if currently unavailable)
• Product becomes unavailable (if currently in stock){shop_link}"""
            logger.info(f"User {user_id} subscribed to product {product.id} via /{number}")
        
        await session.commit()
        await update.message.reply_text(message, parse_mode=constants.ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error in number command handler: {e}")
        await update.message.reply_text("An error occurred. Please try again.")

async def send_notification(context: ContextTypes.DEFAULT_TYPE, product: Product, user_id: str):
    """Send Telegram notification to a subscribed user"""
    try:
        message = format_notification_message(product)
        await context.bot.send_message(chat_id=user_id, text=message, parse_mode=constants.ParseMode.HTML)
        logger.info(f"Notification sent to user {user_id} for product {product.name}")
    except Exception as e:
        logger.error(f"Failed to send notification to {user_id}: {e}")
