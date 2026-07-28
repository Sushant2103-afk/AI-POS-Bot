from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event
from app.core.config import settings

db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# For SQLite databases, allow access from multiple threads
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True
)

# Enforce SQLite foreign key constraints explicitly
if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def auto_migrate_db():
    """
    Safely inspects database tables and adds any missing columns or tables
    for Multi-Roadmap Management backward compatibility.
    """
    from app.database.base_class import Base
    from app.models import core, roadmap  # noqa
    from sqlalchemy import inspect, text

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    if "roadmaps" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("roadmaps")]
        with engine.connect() as conn:
            if "status" not in columns:
                conn.execute(text("ALTER TABLE roadmaps ADD COLUMN status VARCHAR DEFAULT 'active'"))
                conn.execute(text("UPDATE roadmaps SET status = 'active' WHERE is_active = 1 OR is_active IS NULL"))
                conn.execute(text("UPDATE roadmaps SET status = 'paused' WHERE is_active = 0"))
            if "priority" not in columns:
                conn.execute(text("ALTER TABLE roadmaps ADD COLUMN priority INTEGER DEFAULT 1"))
            if "category" not in columns:
                conn.execute(text("ALTER TABLE roadmaps ADD COLUMN category VARCHAR DEFAULT 'General'"))
            if "schedule_type" not in columns:
                conn.execute(text("ALTER TABLE roadmaps ADD COLUMN schedule_type VARCHAR DEFAULT 'daily'"))
            if "schedule_days" not in columns:
                conn.execute(text("ALTER TABLE roadmaps ADD COLUMN schedule_days VARCHAR DEFAULT '[0,1,2,3,4,5,6]'"))
            conn.commit()

auto_migrate_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

