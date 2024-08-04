import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import class_mapper

Base = declarative_base()

class Wrapper():
    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in class_mapper(self.__class__).mapped_table.c}

class BotUser(Base, Wrapper):
    __tablename__ = "bot_users"

    id          = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    uid         = sa.Column(sa.VARCHAR(100), nullable=False)
    is_role     = sa.Column(sa.Integer, nullable=True, default=0)
    priv_level  = sa.Column(sa.Integer, nullable=False)