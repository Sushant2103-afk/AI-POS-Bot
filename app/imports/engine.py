import os
import shutil
import hashlib
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database.base import Base, Users  # noqa
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks as DBTasks
from app.imports.parser import universal_parser
from app.ai.service import get_ai_service
from app.core.logging import logger

# --- Pydantic Schemas for Import Validation ---

class TaskImportSchema(BaseModel):
    title: str
    description: Optional[str] = None
    estimated_minutes: int = 60
    priority: str = "medium" # high, medium, low
    energy_level: str = "medium" # high, medium, low

class TopicImportSchema(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    estimated_hours: float = 0.0
    energy_level: str = "medium"
    tasks: List[TaskImportSchema] = Field(default_factory=list)

class WeekImportSchema(BaseModel):
    week_number: int
    title: str
    target_hours: float = 0.0
    topics: List[TopicImportSchema] = Field(default_factory=list)

class MonthImportSchema(BaseModel):
    month_number: int
    title: str
    target_hours: float = 0.0
    weeks: List[WeekImportSchema] = Field(default_factory=list)

class RoadmapImportSchema(BaseModel):
    title: str = "Curriculum Roadmap"
    description: Optional[str] = None
    months: List[MonthImportSchema] = Field(default_factory=list)

# --- Ai Parsing Instruction ---

SYSTEM_INSTRUCTION = """
You are an AI SDE Placement Roadmap Extractor. Your task is to analyze unstructured curriculum or preparation roadmaps and convert them into a structured JSON hierarchy.
Divide the timeline chronologically into Months (starting with month_number: 1) and Weeks (week_number: 1, 2, 3...).
Under each week, extract the key Topics (e.g. Dynamic Programming) and estimated_hours.
Under each topic, extract the concrete Tasks (e.g. Solve LeetCode 70) and estimated_minutes.

Classify:
- priority: 'high', 'medium', or 'low'.
- energy_level: 'high' for highly conceptual tasks (DP, graph algorithms, complex system design) or 'low' for revisions, reading, query writing, theory.

Output only the final JSON object matching the requested schema. No explanation or code block wrapper.
"""

# --- Import Engine Implementation ---

class ImportEngine:
    def __init__(self, db: Session):
        self.db = db
        self.ai_service = get_ai_service()

    def import_curriculum(
        self,
        user_id: int,
        content: str,
        file_type: str = "markdown",
        filename: str = "curriculum.txt",
        title: Optional[str] = None
    ) -> Roadmaps:
        """Alias method for curriculum content import."""
        extracted_title = title or filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').title()
        return self.import_roadmap(
            user_id=user_id,
            raw_text=content,
            title=extracted_title
        )

    def import_roadmap_text(
        self,
        user_id: int,
        raw_text: str,
        title: Optional[str] = None,
        category: str = "General",
        priority: int = 1,
        schedule_type: str = "daily",
        schedule_days: str = "[0,1,2,3,4,5,6]"
    ) -> Roadmaps:
        """Alias method for raw text roadmap import."""
        return self.import_roadmap(
            user_id=user_id,
            raw_text=raw_text,
            title=title,
            category=category,
            priority=priority,
            schedule_type=schedule_type,
            schedule_days=schedule_days
        )

    def _normalize_parsed_json(self, parsed_json: dict, title: Optional[str] = None) -> dict:
        if not isinstance(parsed_json, dict):
            return {"title": title or "Curriculum Roadmap", "months": []}

        if "roadmap" in parsed_json and isinstance(parsed_json["roadmap"], dict):
            parsed_json = parsed_json["roadmap"]
        elif "data" in parsed_json and isinstance(parsed_json["data"], dict):
            parsed_json = parsed_json["data"]

        if title:
            parsed_json["title"] = title
        elif "title" not in parsed_json or not parsed_json["title"]:
            parsed_json["title"] = "Curriculum Roadmap"

        if "months" not in parsed_json or not parsed_json["months"]:
            if "weeks" in parsed_json and parsed_json["weeks"]:
                parsed_json["months"] = [{
                    "month_number": 1,
                    "title": "Month 1",
                    "target_hours": 0.0,
                    "weeks": parsed_json["weeks"]
                }]
            elif "topics" in parsed_json and parsed_json["topics"]:
                parsed_json["months"] = [{
                    "month_number": 1,
                    "title": "Month 1",
                    "target_hours": 0.0,
                    "weeks": [{
                        "week_number": 1,
                        "title": "Week 1",
                        "target_hours": 0.0,
                        "topics": parsed_json["topics"]
                    }]
                }]
            elif "tasks" in parsed_json and parsed_json["tasks"]:
                parsed_json["months"] = [{
                    "month_number": 1,
                    "title": "Month 1",
                    "target_hours": 0.0,
                    "weeks": [{
                        "week_number": 1,
                        "title": "Week 1",
                        "target_hours": 0.0,
                        "topics": [{
                            "title": parsed_json.get("title", "Core Syllabus Topics"),
                            "description": "Extracted study topics",
                            "priority": "medium",
                            "estimated_hours": 4.0,
                            "energy_level": "medium",
                            "tasks": parsed_json["tasks"]
                        }]
                    }]
                }]

        for m in parsed_json.get("months", []):
            if "weeks" not in m or not m["weeks"]:
                if "topics" in m and m["topics"]:
                    m["weeks"] = [{
                        "week_number": 1,
                        "title": "Week 1",
                        "target_hours": 0.0,
                        "topics": m["topics"]
                    }]

        return parsed_json

    def _fallback_parse_text(self, content_text: str, title: str) -> RoadmapImportSchema:
        lines = [line.strip() for line in content_text.splitlines() if line.strip()]
        topics = []
        current_topic_title = "Core Concepts and Fundamentals"
        current_tasks = []

        for line in lines:
            if line.startswith("#") or line.lower().startswith("day") or line.lower().startswith("module") or line.lower().startswith("section") or line.endswith(":"):
                clean_title = line.lstrip("#").rstrip(":").strip()
                if current_tasks:
                    topics.append(TopicImportSchema(
                        title=current_topic_title,
                        description="Parsed from text syllabus",
                        priority="medium",
                        estimated_hours=len(current_tasks) * 1.0,
                        energy_level="medium",
                        tasks=current_tasks
                    ))
                    current_tasks = []
                current_topic_title = clean_title
            else:
                task_title = line.lstrip("-*1;234567890. ").strip()
                if task_title and len(task_title) > 2:
                    current_tasks.append(TaskImportSchema(
                        title=task_title[:100],
                        description=f'Study task from {title}',
                        estimated_minutes=60,
                        priority="medium",
                        energy_level="medium"
                    ))

        if current_tasks:
            topics.append(TopicImportSchema(
                title=current_topic_title,
                description="Parsed from text syllabus",
                priority="medium",
                estimated_hours=len(current_tasks) * 1.0,
                energy_level="medium",
                tasks=current_tasks
            ))

        if not topics:
            topics.append(TopicImportSchema(
                title="Curriculum Core Tasks",
                description="Imported syllabus tasks",
                priority="medium",
                estimated_hours=2.0,
                energy_level="medium",
                tasks=[
                    TaskImportSchema(
                        title=f"Review {title} Syllabus Materials",
                        description="Initial study session",
                        estimated_minutes=60,
                        priority="high",
                        energy_level="medium"
                    )
                ]
            ))

        month = MonthImportSchema(
            month_number=1,
            title="Month 1",
            target_hours=sum(t.estimated_hours for t in topics),
            weeks=[
                WeekImportSchema(
                    week_number=1,
                    title="Week 1",
                    target_hours=sum(t.estimated_hours for t in topics),
                    topics=topics
                )
            ]
        )
        return RoadmapImportSchema(title=title, months=[month])

    def import_roadmap(
        self,
        user_id: int,
        file_path: Optional[str] = None,
        raw_text: Optional[str] = None,
        title: Optional[str] = None,
        category: str = "General",
        priority: int = 1,
        schedule_type: str = "daily",
        schedule_days: str = "[0,1,2,3,4,5,6]",
        replace: bool = False
    ) -> Roadmaps:
        """
        Process a document or raw text import, extract curriculum data via LLM, 
        validate against Pydantic model, and persist as an independent roadmap.
        """
        if not file_path and not raw_text:
            raise ValueError("Either file_path or raw_text must be provided for import.")

        # 1. Extract raw text from target source
        if file_path:
            content_text = universal_parser.extract_text(file_path)
            saved_path = self._store_file_locally(file_path)
            logger.info(f"Source file copied locally to: {saved_path}")
        else:
            content_text = raw_text
            saved_path = None

        # 2. Extract structured content using LLM
        prompt = f"Extract a structured roadmap from the following source text:\n\n{content_text}"
        logger.info("Sending document text to AI service for structured parsing...")
        parsed_json = self.ai_service.generate_json(
            prompt=prompt,
            system_instruction=SYSTEM_INSTRUCTION
        )

        parsed_json = self._normalize_parsed_json(parsed_json, title)

        # 3. Validate extraction schema via Pydantic
        logger.info("Validating extracted data structure...")
        if isinstance(parsed_json, dict):
            if title:
                parsed_json["title"] = title
            elif "title" not in parsed_json or not parsed_json["title"]:
                parsed_json["title"] = "Curriculum Roadmap"
        roadmap_data = RoadmapImportSchema(**parsed_json)

        total_tasks = sum(
            len(t_data.tasks)
            for m_data in roadmap_data.months
            for w_data in m_data.weeks
            for t_data in w_data.topics
        )

        if total_tasks == 0:
            logger.info("AI extracted 0 tasks. Running rule-based text fallback parser...")
            roadmap_data = self._fallback_parse_text(content_text, title or "Curriculum Roadmap")

        # 4. Handle replacement option if explicitly requested
        if replace:
            existing_roadmaps = self.db.query(Roadmaps).filter(
                Roadmaps.user_id == user_id,
                Roadmaps.title == roadmap_data.title
            ).all()
            for old_roadmap in existing_roadmaps:
                old_roadmap.status = "archived"
                old_roadmap.is_active = False
                self.db.add(old_roadmap)

        # Keep existing roadmaps active so multiple roadmaps coexist

        # 5. Persist Relational Structure as Independent Roadmap
        logger.info(f"Writing roadmap '{roadmap_data.title}' into database...")
        db_roadmap = Roadmaps(
            user_id=user_id,
            title=roadmap_data.title,
            description=roadmap_data.description,
            file_path=saved_path,
            is_active=True,
            status="active",
            priority=1,
            category=category or "General",
            schedule_type=schedule_type or "daily",
            schedule_days=schedule_days or "[0,1,2,3,4,5,6]"
        )
        self.db.add(db_roadmap)
        self.db.flush()

        for m_data in roadmap_data.months:
            db_month = Months(
                roadmap_id=db_roadmap.id,
                month_number=m_data.month_number,
                title=m_data.title,
                target_hours=m_data.target_hours
            )
            self.db.add(db_month)
            self.db.flush()

            for w_data in m_data.weeks:
                db_week = Weeks(
                    month_id=db_month.id,
                    week_number=w_data.week_number,
                    title=w_data.title,
                    target_hours=w_data.target_hours
                )
                self.db.add(db_week)
                self.db.flush()

                for t_data in w_data.topics:
                    db_topic = Topics(
                        roadmap_id=db_roadmap.id,
                        week_id=db_week.id,
                        title=t_data.title,
                        description=t_data.description,
                        priority=t_data.priority,
                        estimated_hours=t_data.estimated_hours,
                        energy_level=t_data.energy_level
                    )
                    self.db.add(db_topic)
                    self.db.flush()

                    for task_data in t_data.tasks:
                        db_task = DBTasks(
                            topic_id=db_topic.id,
                            title=task_data.title,
                            description=task_data.description,
                            estimated_minutes=task_data.estimated_minutes,
                            priority=task_data.priority,
                            energy_level=task_data.energy_level,
                            is_completed=False
                        )
                        self.db.add(db_task)

        self.db.commit()
        logger.info(f"Roadmap ID {db_roadmap.id} ({db_roadmap.title}) successfully created!")
        return db_roadmap

    def duplicate_roadmap(self, user_id: int, noadmap_id: int) -> Roadmaps:
        """Create a duplicate copy of an existing roadmap."""
        source = self.db.query(Roadmaps).filter(
            Roadmaps.id == noadmap_id,
            Roadmaps.user_id == user_id
        ).first()
        if not source:
            raise ValueError(f"Roadmap ID {roadmap_id} not found.")

        new_roadmap = Roadmaps(
            user_id=user_id,
            title=f"{source.title} (Copy)",
            description=source.description,
            file_path=source.file_path,
            is_active=True,
            status="active",
            priority=source.priority,
            category=source.category,
            schedule_type=source.schedule_type,
            schedule_days=source.schedule_days
        )
        self.db.add(new_roadmap)
        self.db.flush()

        for month in source.months:
            new_month = Months(
                roadmap_id=new_roadmap.id,
                month_number=month.month_number,
                title=month.title,
                target_hours=month.target_hours
            )
            self.db.add(new_month)
            self.db.flush()

            for week in month.weeks:
                new_week = Weeks(
                    month_id=new_month.id,
                    week_number=week.week_number,
                    title=week.title,
                    target_hours=week.target_hours
                )
                self.db.add(new_week)
                self.db.flush()

                for topic in week.topics:
                    new_topic = Topics(
                        roadmap_id=new_roadmap.id,
                        week_id=new_week.id,
                        title=topic.title,
                        description=topic.description,
                        priority=topic.priority,
                        estimated_hours=topic.estimated_hours,
                        energy_level=topic.energy_level
                    )
                    self.db.add(new_topic)
                    self.db.flush()

                    for task in topic.tasks:
                        new_task = DBTasks(
                            topic_id=new_topic.id,
                            title=task.title,
                            description=task.description,
                            estimated_minutes=task.estimated_minutes,
                            priority=task.priority,
                            energy_level=task.energy_level,
                            is_completed=False
                        )
                        self.db.add(new_task)

        self.db.commit()
        return new_roadmap

    def _store_file_locally(self, src_path: str) -> str:
        """
        Copy src file to configs/../roadmaps/ directory using a content-hash naming convention
        to prevent conflicts and conserve space.
        """
        workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dest_dir = os.path.join(workspace_dir, "roadmaps")
        os.makedirs(dest_dir, exist_ok=True)
        
        # Calculate SHA256 of file content
        hasher = hashlib.sha256()
        with open(src_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        file_hash = hasher.hexdigest()
        
        _, ext = os.path.splitext(src_path.lower())
        dest_filename = f"{file_hash}{ext}"
        dest_path = os.path.join(dest_dir, dest_filename)
        
        # Copy file if it doesn't already exist in destination
        if not os.path.exists(dest_path):
            shutil.copy2(src_path, dest_path)
            
        return dest_path
