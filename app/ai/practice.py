import urllib.parse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.core.logging import logger

class PracticePlatform(BaseModel):
    name: str
    url: str
    description: str

class PracticeRecommendation(BaseModel):
    task: str
    topic: str
    is_practice_required: bool
    practice_category: str
    estimated_practice_duration: str
    difficulty: str
    platforms: List[PracticePlatform]

def analyze_smart_practice(task_title: str, topic_title: str = "General Study", estimated_minutes: int = 45, priority: str = "medium", energy_level: str = "medium") -> PracticeRecommendation:
    """
    Detects whether a study topic requires practical hands-on exercises,
    and returns tailored free platforms, exercises, estimated practice duration,
    and difficulty level.
    """
    text_combined = (task_title + " " + topic_title).lower()
    encoded_query = urllib.parse.quote_plus(f"{topic_title} {task_title}")

    # Determine Difficulty
    p_low = (priority or "medium").lower()
    e_low = (energy_level or "medium").lower()
    if p_low == "high" or e_low == "high":
        difficulty = "Intermediate"
    elif "advanced" in text_combined or "expert" in text_combined or "hard" in text_combined:
        difficulty = "Advanced"
    else:
        difficulty = "Beginner"

    # Determine Estimated Practice Duration
    mins = estimated_minutes or 45
    if mins >= 60:
        practice_duration = f"{mins - 15}–{mins + 30} minutes"
    else:
        practice_duration = f"{max(15, mins - 10)}–{mins + 15} minutes"

    # Theory-only detection
    theory_keywords = ["ethics", "history of", "overview", "introduction to cs history", "legal compliance", "license", "non-coding"]
    if any(tk in text_combined for tk in theory_keywords) and not any(pk in text_combined for pk in ["code", "solve", "build", "lab", "practice"]):
        return PracticeRecommendation(
            task=task_title,
            topic=topic_title,
            is_practice_required=False,
            practice_category="Theory Only",
            estimated_practice_duration="0 minutes (Conceptual Study)",
            difficulty=difficulty,
            platforms=[
                PracticePlatform(
                    name="Official Documentation & Conceptual Reading",
                    url=f"https://www.google.com/search?q={encoded_query}+documentation",
                    description="Theory-only topic. Review concepts, architectural principles, and notes."
                )
            ]
        )

    # Domain 1: DSA (Data Structures & Algorithms)
    dsa_keywords = ["dsa", "data structure", "algorithm", "binary search", "tree", "graph", "dynamic programming", "leetcode", "sorting", "array", "linked list", "stack", "queue", "heap", "two sum"]
    if any(dk in text_combined for dk in dsa_keywords):
        return PracticeRecommendation(
            task=task_title,
            topic=topic_title,
            is_practice_required=True,
            practice_category="DSA",
            estimated_practice_duration=practice_duration,
            difficulty=difficulty,
            platforms=[
                PracticePlatform(
                    name="LeetCode",
                    url=f"https://leetcode.com/problemset/all/?search={encoded_query}",
                    description="Solve interactive algorithmic problems and test edge cases."
                ),
                PracticePlatform(
                    name="NeetCode",
                    url="https://neetcode.io/roadmap",
                    description="Structured DSA roadmap with visual problem breakdowns."
                ),
                PracticePlatform(
                    name="GeeksforGeeks",
                    url=f"https://www.geeksforgeeks.org/search/?q={encoded_query}",
                    description="Theory guides, complexity analysis, and practice problems."
                )
            ]
        )

    # Domain 2: Python
    python_keywords = ["python", "import module", "package", "pytest", "fastapi", "flask", "django", "pip"]
    if any(pk in text_combined for pk in python_keywords):
        return PracticeRecommendation(
            task=task_title,
            topic=topic_title,
            is_practice_required=True,
            practice_category="Python",
            estimated_practice_duration=practice_duration,
            difficulty=difficulty,
            platforms=[
                PracticePlatform(
                    name="Exercism",
                    url="https://exercism.org/tracks/python",
                    description="Free mentor-guided interactive Python coding tracks and exercises."
                ),
                PracticePlatform(
                    name="HackerRank",
                    url="https://www.hackerrank.com/domains/python",
                    description="Hands-on Python domain challenges covering syntax, data types, and modules."
                ),
                PracticePlatform(
                    name="Official Documentation",
                    url="https://docs.python.org/3/",
                    description="Official Python language reference, standard library docs, and tutorials."
                )
            ]
        )

    # Domain 3: SQL
    sql_keywords = ["sql", "database", "query", "postgres", "mysql", "sqlite", "join", "schema"]
    if any(sk in text_combined for sk in sql_keywords):
        return PracticeRecommendation(
            task=task_title,
            topic=topic_title,
            is_practice_required=True,
            practice_category="SQL",
            estimated_practice_duration=practice_duration,
            difficulty=difficulty,
            platforms=[
                PracticePlatform(
                    name="SQLBolt",
                    url="https://sqlbolt.com/",
                    description="Free interactive SQL lessons and in-browser database queries."
                ),
                PracticePlatform(
                    name="Mode SQL Tutorial",
                    url="https://mode.com/sql-tutorial/",
                    description="Comprehensive real-world data analytics SQL exercises."
                ),
                PracticePlatform(
                    name="HackerRank SQL",
                    url="https://www.hackerrank.com/domains/sql",
                    description="Interactive SQL challenges from Basic Select to Complex Joins."
                )
            ]
        )

    # Domain 4: AI/ML
    aiml_keywords = ["ai", "ml", "machine learning", "deep learning", "numpy", "pandas", "pytorch", "tensorflow", "scikit-learn", "data science", "neural network", "kaggle"]
    if any(ak in text_combined for ak in aiml_keywords):
        return PracticeRecommendation(
            task=task_title,
            topic=topic_title,
            is_practice_required=True,
            practice_category="AI/ML",
            estimated_practice_duration=practice_duration,
            difficulty=difficulty,
            platforms=[
                PracticePlatform(
                    name="Kaggle",
                    url="https://www.kaggle.com/learn",
                    description="Hands-on micro-courses and interactive Jupyter notebooks."
                ),
                PracticePlatform(
                    name="Google Colab",
                    url="https://colab.research.google.com/",
                    description="Free cloud GPU/TPU Jupyter notebook environment for model training."
                ),
                PracticePlatform(
                    name="scikit-learn Documentation",
                    url="https://scikit-learn.org/stable/",
                    description="Official machine learning API reference, tutorials, and examples."
                )
            ]
        )

    # Domain 5: System Design
    sd_keywords = ["system design", "architecture", "microservice", "distributed system", "scalability", "load balancer", "caching", "message queue", "sharding"]
    if any(sdk in text_combined for sdk in sd_keywords):
        return PracticeRecommendation(
            task=task_title,
            topic=topic_title,
            is_practice_required=True,
            practice_category="System Design",
            estimated_practice_duration=practice_duration,
            difficulty=difficulty,
            platforms=[
                PracticePlatform(
                    name="ByteByteGo",
                    url="https://bytebytego.com/",
                    description="Visual system design guides, architectural diagrams, and articles."
                ),
                PracticePlatform(
                    name="System Design Primer",
                    url="https://github.com/donnemartin/system-design-primer",
                    description="Open-source interactive guide to designing large-scale systems."
                )
            ]
        )

    # Universal Practical Default
    return PracticeRecommendation(
        task=task_title,
        topic=topic_title,
        is_practice_required=True,
        practice_category="General Practice",
        estimated_practice_duration=practice_duration,
        difficulty=difficulty,
        platforms=[
            PracticePlatform(
                name="freeCodeCamp",
                url="https://www.freecodecamp.org/",
                description="Interactive hands-on coding curriculum and web development labs."
            ),
            PracticePlatform(
                name="HackerRank & Exercism",
                url="https://www.hackerrank.com/",
                description="Domain-specific practice problems and interactive code submissions."
            ),
            PracticePlatform(
                name="GitHub Repositories",
                url=f"https://github.com/search?q={encoded_query}",
                description="Hands-on project repositories, starter code, and practical exercises."
            )
        ]
    )
