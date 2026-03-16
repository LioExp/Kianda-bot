from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(30), unique=True, index=True, nullable=False)
    name = Column(String(120))
    plan = Column(String(20), default="basic")
    subscription_end = Column(DateTime, nullable=True)
    balance = Column(Float, default=0.0)
    state = Column(String(40), default="new")
    state_data = Column(JSON, default=dict)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    whatsapp_id = Column(String(60), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    owner_phone = Column(String(30), nullable=False)
    owner_balance = Column(Float, default=0.0)
    commission_rate = Column(Float, default=0.05)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    short_code = Column(String(12), unique=True, index=True, nullable=False)
    name = Column(String(200))
    description = Column(Text)
    price = Column(Float, nullable=False)
    media_url = Column(String(500))
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    vendor = relationship("Vendor")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product")
    group = relationship("Group")


class Click(Base):
    __tablename__ = "clicks"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    ip_address = Column(String(45))
    user_agent = Column(String(300))
    timestamp = Column(DateTime, default=datetime.utcnow)


class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    buyer_phone = Column(String(30), nullable=False)
    amount = Column(Float, nullable=False)
    vendor_receives = Column(Float, default=0.0)
    group_receives = Column(Float, default=0.0)
    platform_receives = Column(Float, default=0.0)
    confirmed_at = Column(DateTime, default=datetime.utcnow)