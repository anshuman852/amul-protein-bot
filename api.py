import logging
import aiohttp
from datetime import datetime
from config import API_URL, HOMEPAGE_URL, PREFERENCES_URL, HEADERS

logger = logging.getLogger(__name__)

# Global session for API requests
api_session = None

async def refresh_cookie(session):
    """Get and validate session cookie"""
    try:
        logger.info("Refreshing API session cookie...")
        
        # First request to get jsessionid
        async with session.get(HOMEPAGE_URL, headers=HEADERS) as resp:
            if resp.status != 200:
                logger.error(f"Failed to get homepage: {resp.status}")
                return False
            
            cookies = session.cookie_jar.filter_cookies(HOMEPAGE_URL)
            for key, cookie in cookies.items():
                logger.debug(f"Received cookie: {key}={cookie.value}")

        # Validate cookie by setting preferences
        payload = {
            "data": {
                "store": "gujarat"
            }
        }

        async with session.put(PREFERENCES_URL, json=payload, headers=HEADERS) as resp:
            if resp.status != 200:
                logger.error(f"Cookie validation failed: {resp.status}")
                return False
            logger.info("API session cookie validated successfully")
            return True

    except Exception as e:
        logger.error(f"Error refreshing cookie: {e}")
        return False

async def init_api_session():
    """Initialize API session with valid cookie"""
    global api_session
    if api_session:
        await api_session.close()
    
    api_session = aiohttp.ClientSession()
    if await refresh_cookie(api_session):
        return True
    
    await api_session.close()
    api_session = None
    return False

async def get_products():
    """Fetch all products from API"""
    global api_session
    
    try:
        # Initialize session if needed
        if not api_session:
            if not await init_api_session():
                logger.error("Failed to initialize API session")
                return []
        
        async with api_session.get(API_URL, headers=HEADERS) as response:
            if response.status != 200:
                # Try refreshing cookie on error
                if await refresh_cookie(api_session):
                    async with api_session.get(API_URL, headers=HEADERS) as retry_response:
                        if retry_response.status != 200:
                            logger.error(f"API request failed after cookie refresh: {retry_response.status}")
                            return []
                        data = await retry_response.json()
                else:
                    logger.error(f"API request failed: {response.status}")
                    return []
            else:
                data = await response.json()
            
            products = data.get('data', [])
            logger.info(f"Fetched {len(products)} products from API")
            return products

    except Exception as e:
        logger.error(f"Failed to fetch products from API: {e}")
        return []

async def cleanup():
    """Close API session"""
    global api_session
    if api_session:
        await api_session.close()
        api_session = None