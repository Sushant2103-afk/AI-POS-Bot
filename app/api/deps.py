from fastapi import Header, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.session import SessionLocal
from app.models.core import Users
from typing import Generator

def get_db() -> Generator[Session, None, None]:
    """
    SQLAlchemy database session dependency.
    Yields a session and closes it upon request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user_id(
    x_user_id: int = Header(1, alias="X-User-ID"),
    db: Session = Depends(get_db)
) -> int:
    """
    Dependency to resolve the current active user ID from the 'X-User-ID' header.
    Automatically creates a default user if the ID is 1 and no user exists.
    """
    user = db.query(Users).filter(Users.id == x_user_id).first()
    if not user:
        if x_user_id == 1:
            user = Users(name="Default User", email="default@example.com")
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {x_user_id} not found"
            )
    return user.id
