"""
Database models for RSS & Email Aggregator using SQLAlchemy
"""

from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

# Create SQLAlchemy base class
Base = declarative_base()


class Item(Base):
    """
    Model representing a single RSS feed item or email newsletter item
    """

    __tablename__ = "items"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Item title
    title = Column(String(500), nullable=False)

    # Item URL/link (must be unique to prevent duplicates)
    link = Column(String(1000), nullable=False, unique=True)

    # Publication timestamp
    published = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Item summary/description/body content
    summary = Column(Text, nullable=True)

    # Source identifier (RSS feed name or "email")
    source = Column(String(100), nullable=False)

    # Additional metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Item(id={self.id}, title='{self.title[:50]}...', source='{self.source}', published={self.published})>"

    def to_dict(self):
        """Convert item to dictionary for easy serialization"""
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "published": self.published,
            "summary": self.summary,
            "source": self.source,
            "created_at": self.created_at,
        }


# Database engine and session setup
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)


def get_db_session():
    """Get a database session"""
    return SessionLocal()


def init_database():
    """Initialize the database by creating tables"""
    try:
        create_tables()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise


if __name__ == "__main__":
    # Initialize database when run directly
    init_database()
