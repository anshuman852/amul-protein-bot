from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, MetaData
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

# Create base with naming convention for foreign keys
convention = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}
metadata = MetaData(naming_convention=convention)

Base = declarative_base(metadata=metadata)

class Product(Base):
    """Product information"""
    __tablename__ = 'products'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Integer)
    sku = Column(String)
    alias = Column(String)
    available = Column(Boolean, default=False)
    last_checked = Column(DateTime, default=datetime.utcnow)
    subscriptions = relationship("Subscription", back_populates="product")

class User(Base):
    """Telegram user information"""
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True)
    first_seen = Column(DateTime, default=datetime.utcnow)
    subscriptions = relationship("Subscription", back_populates="user")

class Subscription(Base):
    """Product subscriptions for users"""
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    product_id = Column(String, ForeignKey('products.id'), nullable=False)
    subscribed_at = Column(DateTime, default=datetime.utcnow)
    last_notified_at = Column(DateTime, nullable=True)  # When was the last notification sent
    notified = Column(Boolean, default=False)  # Has current stock status been notified
    last_stock_status = Column(Boolean, default=False)  # Last known stock status
    
    user = relationship("User", back_populates="subscriptions")
    product = relationship("Product", back_populates="subscriptions")