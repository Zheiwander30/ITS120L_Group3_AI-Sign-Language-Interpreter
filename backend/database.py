import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 1. Check Railway's variable first, fallback to local if not found
DATABASE_URL = os.getenv("DATABASE_URL")

# 2. If it's the default Railway link, we need to fix the 'mysql+pymysql' prefix
if DATABASE_URL and DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)

# 3. Fallback for your local development (your old line)
if not DATABASE_URL:
    DATABASE_URL = "mysql+pymysql://root:root@localhost:3307/asl_db"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()
