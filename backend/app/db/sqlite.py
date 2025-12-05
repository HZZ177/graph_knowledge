import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 数据库文件位于 backend/app/app.db
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "app.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_DB_PATH}"

# sqlite 需要 check_same_thread=False 才能在多线程环境中使用同一个连接
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    from typing import Generator

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
