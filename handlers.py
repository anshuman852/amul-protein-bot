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
    """List all products with subscription buttons"""
    try:
        user_id = str(update.effective_user.id)
        
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
        
        # Create keyboard with product buttons
        keyboard = []
        for product in products:
            # Check if user is subscribed
            is_subscribed = any(sub.user_id == user_id and not sub.notified for sub in product.subscriptions)
            status = "🔴 Out of Stock" if not product.available else "🟢 In Stock"
            sub_status = "✅ Subscribed" if is_subscribed else ""
            
            # Format price in rupees
            price = f"₹{product.price}"
            
            button = InlineKeyboardButton(
                f"{product.name} - {price} ({status}) {sub_status}",
                callback_data=f"toggle_{product.id}"
            )
            keyboard.append([button])
        
        if keyboard:
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🛒 <b>Product Catalog</b>\n\n"
                "📱 Select products to get notified when they're back in stock\n"
                "👆 Click on a product to subscribe/unsubscribe\n\n"
                "🟢 = In Stock | 🔴 = Out of Stock | ✅ = Subscribed",
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
    """Handle button presses for product subscriptions"""
    query = update.callback_query
    await query.answer()
    
    product_id = query.data.replace("toggle_", "")
    user_id = str(query.from_user.id)
    
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
            product_link = f"https://shop.amul.com/en/product/{product.alias}"
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

async def send_notification(context: ContextTypes.DEFAULT_TYPE, product: Product, user_id: str):
    """Send Telegram notification to a subscribed user"""
    try:
        message = format_notification_message(product)
        await context.bot.send_message(chat_id=user_id, text=message, parse_mode=constants.ParseMode.HTML)
        logger.info(f"Notification sent to user {user_id} for product {product.name}")
    except Exception as e:
        logger.error(f"Failed to send notification to {user_id}: {e}")
