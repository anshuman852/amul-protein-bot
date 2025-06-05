[Previous content unchanged until line 494]

# Bot command descriptions
COMMANDS = {
    'start': 'Start the bot and get welcome message',
    'products': 'Browse and subscribe to products',
    'mysubs': 'View your subscribed products',
    'stock': 'Check current stock status of all products'
}

def categorize_products(products):
    """Group products by category and variants"""
    categories = {
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
        elif "milkshake" in name:
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

async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current stock status of all products"""
    try:
        async with async_session() as session:
            # Get all products ordered by availability and name
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
            
            # Categorize products
            categories = categorize_products(products)
            
            # Build message
            message = "📊 Product Categories\n\n"
            
            for category_name, category_data in categories.items():
                has_products = False
                category_text = []
                
                # Add category header
                category_text.append(f"{category_data['emoji']} {category_name}")
                
                # Add variants with products
                for variant, products in category_data['variants'].items():
                    if products:
                        has_products = True
                        category_text.append(f"\n{variant}:")
                        category_text.extend(f"• {p}" for p in sorted(products))
                
                if has_products:
                    message += "\n".join(category_text) + "\n\n"
            
            # Add timing information
            if last_check_time:
                message += f"\nLast updated: {last_check_time.strftime('%Y-%m-%d %H:%M')}"
            
            next_check = datetime.now() + timedelta(seconds=CHECK_INTERVAL)
            message += f"\nNext check in: {CHECK_INTERVAL//60} minutes (around {next_check.strftime('%H:%M')})"
            
            await update.message.reply_text(message)
            
    except Exception as e:
        logger.error(f"Error in stock command: {e}")
        await update.message.reply_text(
            "An error occurred while fetching stock status. Please try again later."
        )

[Rest of the file unchanged]