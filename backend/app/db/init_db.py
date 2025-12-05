from sqlalchemy.orm import Session


def init_db(db: Session) -> None:
    """数据库初始化函数。
    
    当前为空实现，数据库表结构由 SQLAlchemy 模型自动创建。
    如需初始化数据，可在此添加逻辑。
    """
    pass
