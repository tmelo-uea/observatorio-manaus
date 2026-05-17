import os
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

def _build_url():
    # Railway injeta DATABASE_URL automaticamente quando o serviço MySQL é vinculado
    database_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    if database_url:
        # Garante que usa o driver correto
        return re.sub(r"^mysql://", "mysql+mysqlconnector://", database_url)

    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "railway")
    return (
        f"mysql+mysqlconnector://{user}:{password}"
        f"@{host}:{port}/{database}?charset=utf8mb4"
    )

def get_engine():
    url = _build_url()
    # SSL necessário apenas para conexões externas (coletor local via túnel)
    is_internal = "railway.internal" in url
    connect_args = {} if is_internal else {
        "ssl_disabled": False,
        "ssl_verify_cert": False,
        "ssl_verify_identity": False,
    }
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)

engine = get_engine()
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

def get_session():
    return SessionLocal()
