from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 SQLAlchemy ORM model 的共同基类。

    阶段 1 先用手写 migration 落库表；后续补 ORM model 时统一继承
    这个 Base，Alembic autogenerate 才能识别模型元数据。
    """

    pass
