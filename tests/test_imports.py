import os
from app.models.core import Users
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks
from app.imports.engine import ImportEngine
from app.imports.parser import universal_parser

def test_document_parser(tmp_path):
    """
    Verify text extraction for text files.
    """
    txt_file = tmp_path / "curriculum.txt"
    txt_file.write_text("Week 1: Array problems.", encoding="utf-8")
    
    parsed = universal_parser.extract_text(str(txt_file))
    assert "Week 1: Array problems" in parsed

def test_import_engine_workflow(db_session, tmp_path):
    """
    Verify full parsing pipeline and database relational insertion.
    """
    # Initialize user profile
    user = Users(name="Jane", email="jane@example.com")
    db_session.add(user)
    db_session.commit()
    
    # Create input file
    roadmap_file = tmp_path / "placement_syllabus.txt"
    roadmap_file.write_text("Placement roadmap details.", encoding="utf-8")
    
    # Run import engine
    engine = ImportEngine(db_session)
    roadmap = engine.import_roadmap(user_id=user.id, file_path=str(roadmap_file))
    
    # Verify relational insertions
    assert roadmap.title == "Mock SDE Prep Roadmap"
    assert roadmap.is_active is True
    assert roadmap.file_path is not None
    
    months = db_session.query(Months).filter(Months.roadmap_id == roadmap.id).all()
    assert len(months) == 1
    assert months[0].title == "Dynamic Programming & Array Foundations"
    
    weeks = db_session.query(Weeks).filter(Weeks.month_id == months[0].id).all()
    assert len(weeks) == 1
    
    topics = db_session.query(Topics).filter(Topics.week_id == weeks[0].id).all()
    assert len(topics) == 1
    assert topics[0].title == "Climbing Stairs & Array Dictionaries"
    
    tasks = db_session.query(Tasks).filter(Tasks.topic_id == topics[0].id).all()
    assert len(tasks) == 2
    assert tasks[0].title == "Solve LeetCode 70 (Climbing Stairs)"
    assert tasks[1].title == "Solve LeetCode 1 (Two Sum)"

def test_duplicate_roadmap_deactivation(db_session, tmp_path):
    """
    Verify that importing a duplicate roadmap title deactivates the previous active copy.
    """
    user = Users(name="Jane", email="jane@example.com")
    db_session.add(user)
    db_session.commit()
    
    roadmap_file = tmp_path / "placement_syllabus.txt"
    roadmap_file.write_text("Placement roadmap details.", encoding="utf-8")
    
    engine = ImportEngine(db_session)
    
    # Import first time
    r1 = engine.import_roadmap(user_id=user.id, file_path=str(roadmap_file))
    assert r1.is_active is True
    
    # Import second time with replace=True
    r2 = engine.import_roadmap(user_id=user.id, file_path=str(roadmap_file), replace=True)
    assert r2.is_active is True
    
    # Verify r1 is deactivated
    db_session.refresh(r1)
    assert r1.is_active is False

def test_import_curriculum_alias(db_session):
    user = Users(name="CurriculumUser", email="curr@example.com")
    db_session.add(user)
    db_session.commit()
    
    engine = ImportEngine(db_session)
    roadmap = engine.import_curriculum(
        user_id=user.id,
        content="Week 1: Foundations of Python",
        file_type="markdown",
        filename="python_guide.md"
    )
    
    assert roadmap is not None
    assert roadmap.title == "Python Guide"

