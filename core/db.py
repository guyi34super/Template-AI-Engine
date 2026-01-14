# aqee/core/vdb.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import SQLITE_PATH

engine = create_engine(f"sqlite:///{SQLITE_PATH}", future=True, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
Base = declarative_base()

def init_db():
    from . import models  # ensure models are imported
    Base.metadata.create_all(bind=engine)
