import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# 数据库文件位于 backend/app/app.db
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "app.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_DB_PATH}"

# sqlite 需要 check_same_thread=False 才能在多线程环境中使用同一个连接
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 启用 WAL 模式，支持并发读写
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")  # 等待锁释放最多 5 秒
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    from typing import Generator

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
