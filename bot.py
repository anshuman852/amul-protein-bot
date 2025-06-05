import asyncio
import logging
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from config import BOT_TOKEN, DATABASE_URL, CHECK_INTERVAL, COMMANDS
from models import Base, Product, Subscription
from api import get_products, init_api_session, cleanup
from handlers import start, list_products, button_callback, my_subscriptions, stock, send_notification
from utils import create_product_from_api

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set higher log level for other libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Initialize database engine
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def initialize():
    """Initialize database and API session"""
    # Create data directory if it doesn't exist
    if not os.path.exists('data'):
        os.makedirs('data')
        logger.info("Created data directory")

    # Initialize database
    try:
        async with engine.begin() as conn:
            # Create all tables if they don't exist
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created/verified")
                
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    # Initialize API session
    if await init_api_session():
        logger.info("API session initialized successfully")
    else:
        logger.error("Failed to initialize API session")
        raise RuntimeError("API session initialization failed")

async def check_stock(context: ContextTypes.DEFAULT_TYPE):
    """Periodic job to check stock and notify subscribers"""
    try:
        api_products = await get_products()
        logger.info(f"Fetched {len(api_products)} products from API")
        
        if not api_products:
            logger.warning("No products returned from API")
            return
        
        async with async_session() as session:
            await session.begin()
            
            for api_product in api_products:
                from sqlalchemy import select
                from sqlalchemy.orm import selectinload
                
                # Update or create product
                product_query = select(Product).where(Product.id == api_product['_id'])
                result = await session.execute(product_query)
                product = result.scalar_one_or_none()
                
                current_stock_status = api_product['available'] == 1
                
                if not product:
                    product = create_product_from_api(api_product)
                    session.add(product)
                    logger.info(f"Added new product: {product.name}")
                else:
                    # Get all subscriptions for this product
                    subs_query = select(Subscription).where(
                        Subscription.product_id == product.id
                    ).options(selectinload(Subscription.user))
                    
                    result = await session.execute(subs_query)
                    subscriptions = result.scalars().all()
                    
                    for sub in subscriptions:
                        stock_changed = sub.last_stock_status != current_stock_status
                        
                        if stock_changed:
                            if current_stock_status:  # Product became available
                                await send_notification(context, product, sub.user_id)
                                sub.last_notified_at = datetime.utcnow()
                                sub.notified = True
                                logger.info(f"Notified user {sub.user_id} about {product.name} becoming available")
                            else:  # Product went out of stock
                                sub.notified = False  # Reset notification status for next availability
                                logger.info(f"Reset notification status for {sub.user_id} as {product.name} is out of stock")
                            
                            sub.last_stock_status = current_stock_status
                    
                    # Update product details
                    product.price = api_product['price']
                    product.available = current_stock_status
                    product.last_checked = datetime.utcnow()
            
            await session.commit()
            logger.info("Stock check completed successfully")
                
    except Exception as e:
        logger.error(f"Error occurred during stock check: {e}")

def command_wrapper(func):
    """Wrapper to provide database session to command handlers"""
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        async with async_session() as session:
            await session.begin()
            try:
                await func(update, context, session)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Error in {func.__name__}: {e}")
                await update.message.reply_text(
                    "An error occurred. Please try again later."
                )
    return wrapped

def main():
    """Start the bot"""
    try:
        # Initialize everything first
        asyncio.get_event_loop().run_until_complete(initialize())
        
        # Create the Application
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .concurrent_updates(True)
            .build()
        )

        # Add command handlers with session wrapper
        application.add_handler(CommandHandler("start", command_wrapper(start)))
        application.add_handler(CommandHandler("products", command_wrapper(list_products)))
        application.add_handler(CommandHandler("mysubs", command_wrapper(my_subscriptions)))
        application.add_handler(CommandHandler("stock", command_wrapper(stock)))
        application.add_handler(CallbackQueryHandler(command_wrapper(button_callback)))

        # Set bot commands
        async def set_commands():
            await application.bot.set_my_commands([
                (cmd, desc) for cmd, desc in COMMANDS.items()
            ])
        asyncio.get_event_loop().run_until_complete(set_commands())
        logger.info("Bot commands registered")

        # Add periodic stock checker
        application.job_queue.run_repeating(
            check_stock,
            interval=CHECK_INTERVAL,
            first=10  # First run after 10 seconds
        )
        logger.info("Stock checker scheduled")
        logger.info("Bot starting...")

        # Start the bot
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise
    finally:
        # Cleanup API session
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is still running, schedule cleanup
                loop.create_task(cleanup())
            else:
                # If loop is closed, create new one for cleanup
                asyncio.run(cleanup())
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")