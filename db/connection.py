import os
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

def _build_url():
    database_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    if database_url:
        return re.sub(r"^mysql://", "mysql+pymysql://", database_url)

    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "railway")
    return (
        f"mysql+pymysql://{user}:{password}"
        f"@{host}:{port}/{database}?charset=utf8mb4"
    )

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_build_url(), pool_pre_ping=True)
    return _engine

class Base(DeclarativeBase):
    pass

def get_session():
    return sessionmaker(bind=get_engine())()
