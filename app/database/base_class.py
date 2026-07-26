from typing import Any
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    id: Any
    __name__: str

    # Generate table names dynamically from ClassNames
    @declared_attr
    def __tablename__(cls) -> str:
        # Convert PascalCase/camelCase class name to snake_case
        name = cls.__name__
        parts = []
        start = 0
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                parts.append(name[start:i].lower())
                start = i
        parts.append(name[start:].lower())
        return "_".join(parts)

    # Base timestamps present in all database records
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
