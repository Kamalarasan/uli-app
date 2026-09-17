import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError
from app.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI dependency to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def wait_for_db(max_retries: int = None, retry_interval: int = None) -> None:
    """Wait for MariaDB to become available, retrying on failure."""
    max_retries = max_retries or settings.MAX_RETRIES
    retry_interval = retry_interval or settings.RETRY_INTERVAL
    
    logger.info(f"Waiting for database at {settings.DB_HOST}:{settings.DB_PORT}...")
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info(f"Database connection established on attempt {attempt}.")
            return
        except OperationalError as e:
            if attempt < max_retries:
                logger.warning(f"DB not ready (attempt {attempt}/{max_retries}): {e}. Retrying in {retry_interval}s...")
                time.sleep(retry_interval)
            else:
                logger.error(f"Could not connect to database after {max_retries} attempts.")
                raise RuntimeError(f"Database unavailable after {max_retries} retries.") from e

def init_db() -> None:
    """Create all tables."""
    from app.models.orm import Base as ModelBase  # noqa: F401 - imports all models
    ModelBase.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified.")
