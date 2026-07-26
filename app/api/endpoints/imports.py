from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
from app.api.deps import get_db, get_current_user_id
from app.api.schemas import ImportTextRequest, RoadmapResponse
from app.imports.engine import ImportEngine
from app.models.roadmap import Roadmaps
from app.core.logging import logger

router = APIRouter()

@router.post("/file", response_model=RoadmapResponse, status_code=status.HTTP_201_CREATED)
def import_roadmap_file(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Upload a curriculum file (PDF, Word, Excel, Markdown, JSON, Text).
    Extracts text, parses it using the AI placement roadmap engine, and persists it.
    """
    logger.info(f"Received file upload '{file.filename}' for User {user_id}")
    
    # Create a temporary file in the workspace to allow local parsing
    workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    temp_dir = os.path.join(workspace_dir, "tmp_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    
    _, ext = os.path.splitext(file.filename)
    temp_filename = f"{uuid.uuid4()}{ext}"
    temp_path = os.path.join(temp_dir, temp_filename)
    
    try:
        with open(temp_path, "wb") as f:
            f.write(file.file.read())
            
        engine = ImportEngine(db)
        roadmap = engine.import_roadmap(user_id, file_path=temp_path)
        return roadmap
    except Exception as e:
        logger.error(f"Error during file import processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to process and parse roadmap document: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as ex:
                logger.warning(f"Could not remove temporary file {temp_path}: {ex}")

@router.post("/text", response_model=RoadmapResponse, status_code=status.HTTP_201_CREATED)
def import_roadmap_text(
    import_in: ImportTextRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Import a curriculum from raw paste text.
    Parses details using AI and seeds relational database tables.
    """
    logger.info(f"Received raw text roadmap import '{import_in.title}' for User {user_id}")
    try:
        engine = ImportEngine(db)
        roadmap = engine.import_roadmap(user_id, raw_text=import_in.content)
        return roadmap
    except Exception as e:
        logger.error(f"Error during raw text import: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse text roadmap: {str(e)}"
        )

@router.get("/roadmaps", response_model=List[RoadmapResponse])
def get_roadmaps(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Retrieve all roadmaps matching the current user."""
    return db.query(Roadmaps).filter(Roadmaps.user_id == user_id).all()
