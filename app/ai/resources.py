import urllib.parse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.ai.service import get_ai_service
from app.core.logging import logger

class LearningResource(BaseModel):
    category: str
    title: str
    url: str
    description: str

class TaskResourcesResponse(BaseModel):
    task: str
    topic: Optional[str] = None
    resources: List[LearningResource]

RESOURCE_CATEGORIES = [
    "Official Documentation",
    "High-quality Free Tutorial / Article",
    "Free YouTube Video",
    "Interactive Practice Platform",
    "Coding Practice / Problems",
    "Cheat Sheet or Reference"
]

FORBIDDEN_KEYWORDS = ["roadmap", "career path", "learning plan", "study plan", "bootcamp"]

_RESOURCE_CACHE: Dict[str, List[Dict[str, Any]]] = {}


def is_roadmap_task(task_title: str) -> bool:
    """Checks if the user's task title explicitly mentions studying a roadmap."""
    return "roadmap" in task_title.lower()


def clean_and_validate_resources(
    resources: List[Dict[str, Any]],
    task_title: str
) -> List[Dict[str, Any]]:
    """
    Filters and cleans resource recommendations:
    1. Ensures no forbidden keywords (roadmap, career path, learning plan, study plan) appear in title/description
       unless the task itself is explicitly about studying a roadmap.
    2. Removes invalid URLs or generic search placeholders.
    3. Guarantees deduplication.
    """
    allow_roadmap_terms = is_roadmap_task(task_title)
    cleaned = []
    seen_titles = set()

    for r in resources:
        if not isinstance(r, dict):
            continue
        
        title = (r.get("title") or "").strip()
        category = (r.get("category") or "High-quality Free Tutorial / Article").strip()
        url = (r.get("url") or "").strip()
        description = (r.get("description") or "").strip()

        if not title:
            continue

        # Check for forbidden keywords if not allowed
        if not allow_roadmap_terms:
            combined = (title + " " + description).lower()
            if any(forbidden in combined for forbidden in FORBIDDEN_KEYWORDS):
                logger.info(f"Filtering out non-compliant resource containing forbidden keyword: '{title}'")
                continue

        if title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())

        if not url or not url.startswith("http"):
            encoded_title = urllib.parse.quote_plus(f"{task_title} {title}")
            url = f"https://www.google.com/search?q={encoded_title}"

        cleaned.append({
            "category": category,
            "title": title,
            "url": url,
            "description": description or f"High quality free learning resource for {task_title}."
        })

    return cleaned


def get_fallback_resources(
    task_title: str,
    topic_title: Optional[str] = None,
    subject: Optional[str] = None,
    difficulty: Optional[str] = "Beginner"
) -> List[Dict[str, Any]]:
    """
    Generates high-quality, domain-tailored fallback learning resources strictly for the 
    CURRENT STUDY TASK, avoiding overall roadmap/career path recommendations.
    """
    subject_str = subject or topic_title or "General"
    topic_str = topic_title or subject_str
    combined_query = f"{subject_str} {topic_str} {task_title}".strip()
    encoded_query = urllib.parse.quote_plus(f"{task_title} {topic_str}")
    encoded_task = urllib.parse.quote_plus(task_title)
    t_lower = combined_query.lower()

    # 1. Python domain fallbacks
    if "python" in t_lower:
        if "import" in t_lower or "module" in t_lower or "package" in t_lower:
            return [
                {
                    "category": "Official Documentation",
                    "title": "Official Python Documentation: Modules",
                    "url": "https://docs.python.org/3/tutorial/modules.html",
                    "description": "Official guide on defining, importing, and organizing Python modules."
                },
                {
                    "category": "High-quality Free Tutorial / Article",
                    "title": "Real Python: Python Modules and Packages",
                    "url": "https://realpython.com/python-modules-packages/",
                    "description": "Comprehensive tutorial on creating and importing custom modules."
                },
                {
                    "category": "Free YouTube Video",
                    "title": "freeCodeCamp: Python Modules & Imports Explained",
                    "url": f"https://www.youtube.com/results?search_query={encoded_task}+freecodecamp",
                    "description": "Clear visual breakdown of Python import statements and module namespaces."
                },
                {
                    "category": "Interactive Practice Platform",
                    "title": "W3Schools: Python Modules Tutorial & Exercises",
                    "url": "https://www.w3schools.com/python/python_modules.asp",
                    "description": "Browser-based interactive exercises for creating and importing modules."
                },
                {
                    "category": "Coding Practice / Problems",
                    "title": "Exercism Python Track: Modules & Imports",
                    "url": "https://exercism.org/tracks/python",
                    "description": "Hands-on coding exercises to practice modular Python development."
                }
            ]
        else:
            return [
                {
                    "category": "Official Documentation",
                    "title": f"Official Python Documentation: {task_title}",
                    "url": "https://docs.python.org/3/tutorial/",
                    "description": f"Official Python specification and usage guide for {task_title}."
                },
                {
                    "category": "High-quality Free Tutorial / Article",
                    "title": f"Real Python: {task_title} Guide",
                    "url": f"https://realpython.com/search?q={encoded_task}",
                    "description": f"In-depth tutorial and best practices for {task_title} in Python."
                },
                {
                    "category": "Free YouTube Video",
                    "title": f"freeCodeCamp: {task_title} Tutorial",
                    "url": f"https://www.youtube.com/results?search_query=python+{encoded_task}+freecodecamp",
                    "description": f"Video tutorial explaining concepts and code examples for {task_title}."
                },
                {
                    "category": "Interactive Practice Platform",
                    "title": f"W3Schools Python Practice: {task_title}",
                    "url": f"https://www.w3schools.com/python/",
                    "description": f"Interactive practice exercises for {task_title}."
                },
                {
                    "category": "Cheat Sheet or Reference",
                    "title": f"Python {task_title} Quick Reference",
                    "url": f"https://github.com/gto76/python-cheatsheet",
                    "description": f"Quick syntax reference and code snippets for {task_title}."
                }
            ]

    # 2. DSA / Algorithms domain fallbacks
    elif any(k in t_lower for k in ["dsa", "binary search", "algorithm", "data structure", "tree", "graph", "sorting", "linked list", "recursion", "array", "stack", "queue", "heap"]):
        if "binary search" in t_lower:
            return [
                {
                    "category": "Official Documentation",
                    "title": "GeeksforGeeks: Binary Search Algorithm Guide",
                    "url": "https://www.geeksforgeeks.org/binary-search/",
                    "description": "Detailed explanation of binary search, time complexity, and edge cases."
                },
                {
                    "category": "High-quality Free Tutorial / Article",
                    "title": "Striver (takeUforward): Binary Search Guide & Patterns",
                    "url": "https://takeuforward.org/data-structure/binary-search-explained/",
                    "description": "Step-by-step breakdown of binary search implementation patterns."
                },
                {
                    "category": "Free YouTube Video",
                    "title": "NeetCode: Binary Search Explanation & Code Walkthrough",
                    "url": f"https://www.youtube.com/results?search_query=binary+search+neetcode",
                    "description": "Intuitive video explanation of binary search boundaries and code."
                },
                {
                    "category": "Interactive Practice Platform",
                    "title": "LeetCode: Binary Search Problem Set",
                    "url": "https://leetcode.com/problemset/all/?search=binary+search",
                    "description": "Interactive coding practice problems on binary search."
                },
                {
                    "category": "Cheat Sheet or Reference",
                    "title": "Visualgo: Visual Binary Search Animation",
                    "url": "https://visualgo.net/en/bst",
                    "description": "Interactive visual animations demonstrating step-by-step binary search."
                }
            ]
        else:
            return [
                {
                    "category": "Official Documentation",
                    "title": f"GeeksforGeeks: {task_title} Guide",
                    "url": f"https://www.geeksforgeeks.org/search/?q={encoded_task}",
                    "description": f"Technical explanation, code implementations, and complexity analysis for {task_title}."
                },
                {
                    "category": "High-quality Free Tutorial / Article",
                    "title": f"Striver (takeUforward): {task_title} Tutorial",
                    "url": f"https://takeuforward.org/?s={encoded_task}",
                    "description": f"Clear conceptual explanation and problem-solving strategy for {task_title}."
                },
                {
                    "category": "Free YouTube Video",
                    "title": f"NeetCode: {task_title} Video Walkthrough",
                    "url": f"https://www.youtube.com/results?search_query={encoded_task}+neetcode",
                    "description": f"Video tutorial and problem breakdown for {task_title}."
                },
                {
                    "category": "Coding Practice / Problems",
                    "title": f"LeetCode: {task_title} Practice Problems",
                    "url": f"https://leetcode.com/problemset/all/?search={encoded_task}",
                    "description": f"Targeted coding problems for practicing {task_title}."
                },
                {
                    "category": "Cheat Sheet or Reference",
                    "title": f"Tech Interview Handbook: {task_title} Summary",
                    "url": f"https://www.techinterviewhandbook.org/grind75",
                    "description": f"Quick cheat sheet and key patterns for {task_title}."
                }
            ]

    # 3. AI / Machine Learning fallbacks
    elif any(k in t_lower for k in ["ai", "machine learning", "linear regression", "neural network", "deep learning", "scikit", "tensorflow", "pytorch", "model"]):
        if "linear regression" in t_lower:
            return [
                {
                    "category": "Official Documentation",
                    "title": "scikit-learn Documentation: Linear Models",
                    "url": "https://scikit-learn.org/stable/modules/linear_model.html",
                    "description": "Official scikit-learn API guide and examples for Linear Regression."
                },
                {
                    "category": "High-quality Free Tutorial / Article",
                    "title": "Google Machine Learning Crash Course: Linear Regression",
                    "url": "https://developers.google.com/machine-learning/crash-course/first-steps-with-tensorflow/first-steps-with-tensor-fire",
                    "description": "Google's interactive guide on linear regression concepts and loss functions."
                },
                {
                    "category": "Free YouTube Video",
                    "title": "StatQuest: Linear Regression Clearly Explained",
                    "url": "https://www.youtube.com/results?search_query=statquest+linear+regression",
                    "description": "Intuitive step-by-step visual explanation of linear regression fundamentals."
                },
                {
                    "category": "Interactive Practice Platform",
                    "title": "Kaggle Notebooks: Linear Regression Practice",
                    "url": "https://www.kaggle.com/learn/intro-to-machine-learning",
                    "description": "Interactive Python notebook practicing linear regression model training."
                },
                {
                    "category": "Coding Practice / Problems",
                    "title": "Kaggle Housing Prices Competition Notebook",
                    "url": "https://www.kaggle.com/c/house-prices-advanced-regression-techniques",
                    "description": "Hands-on machine learning exercise predicting values with regression models."
                }
            ]
        else:
            return [
                {
                    "category": "Official Documentation",
                    "title": f"scikit-learn / PyTorch Documentation: {task_title}",
                    "url": f"https://scikit-learn.org/stable/search.html?q={encoded_task}",
                    "description": f"Official documentation and syntax reference for {task_title}."
                },
                {
                    "category": "High-quality Free Tutorial / Article",
                    "title": f"Google ML Crash Course: {task_title}",
                    "url": f"https://developers.google.com/machine-learning/crash-course",
                    "description": f"Google's free interactive tutorial covering {task_title}."
                },
                {
                    "category": "Free YouTube Video",
                    "title": f"StatQuest: {task_title} Explained",
                    "url": f"https://www.youtube.com/results?search_query={encoded_task}+statquest",
                    "description": f"Visual explanation of {task_title} math and concepts."
                },
                {
                    "category": "Interactive Practice Platform",
                    "title": f"Kaggle Learn: {task_title} Practice Notebook",
                    "url": f"https://www.kaggle.com/learn",
                    "description": f"Hands-on interactive data science notebooks for {task_title}."
                },
                {
                    "category": "Cheat Sheet or Reference",
                    "title": f"Machine Learning Cheatsheet: {task_title}",
                    "url": "https://github.com/afshinea/stanford-cs-229-machine-learning-cheatsheet",
                    "description": f"Stanford CS229 summary notes and cheat sheets for {task_title}."
                }
            ]

    # 4. Operating Systems / Systems Programming fallbacks
    elif any(k in t_lower for k in ["operating system", "os", "process", "thread", "memory", "paging", "deadlock", "cpu scheduling", "concurrency"]):
        if "process" in t_lower and "thread" in t_lower:
            return [
                {
                    "category": "Official Documentation",
                    "title": "OSTEP Chapter: Processes and Threads",
                    "url": "https://pages.cs.wisc.edu/~remzi/OSTEP/",
                    "description": "Free classic textbook chapter from Operating Systems: Three Easy Pieces."
                },
                {
                    "category": "High-quality Free Tutorial / Article",
                    "title": "GeeksforGeeks: Difference between Process and Thread",
                    "url": "https://www.geeksforgeeks.org/difference-between-process-and-thread/",
                    "description": "Comprehensive comparative table, memory layout, and execution context."
                },
                {
                    "category": "Free YouTube Video",
                    "title": "NPTEL / Gate Smashers: Processes vs Threads Lecture",
                    "url": f"https://www.youtube.com/results?search_query=processes+vs+threads+gate+smashers",
                    "description": "Clear academic lecture covering PCB, thread control blocks, and context switching."
                },
                {
                    "category": "Interactive Practice Platform",
                    "title": "University OS Lecture Notes & Self-Assessment",
                    "url": "https://cs161.org/",
                    "description": "Harvard CS161 open course notes and practice questions on threads and processes."
                },
                {
                    "category": "Cheat Sheet or Reference",
                    "title": "OS Process vs Thread Memory Layout Diagram",
                    "url": "https://github.com/donnemartin/system-design-primer#operating-system-basics",
                    "description": "Quick reference architectural diagrams for processes and threads."
                }
            ]
        else:
            return [
                {
                    "category": "Official Documentation",
                    "title": f"OSTEP Textbook Guide: {task_title}",
                    "url": "https://pages.cs.wisc.edu/~remzi/OSTEP/",
                    "description": f"Free open textbook chapter on {task_title} from Operating Systems: Three Easy Pieces."
                },
                {
                    "category": "High-quality Free Tutorial / Article",
                    "title": f"GeeksforGeeks Operating Systems: {task_title}",
                    "url": f"https://www.geeksforgeeks.org/search/?q={encoded_task}",
                    "description": f"Clear conceptual breakdown and OS architecture guide for {task_title}."
                },
                {
                    "category": "Free YouTube Video",
                    "title": f"Gate Smashers / NPTEL: {task_title} Video Lecture",
                    "url": f"https://www.youtube.com/results?search_query={encoded_task}+gate+smashers",
                    "description": f"Detailed academic lecture explaining {task_title} concepts."
                },
                {
                    "category": "Interactive Practice Platform",
                    "title": f"University OS Notes & Exercises: {task_title}",
                    "url": "https://cs161.org/",
                    "description": f"Course materials and conceptual exercises for {task_title}."
                },
                {
                    "category": "Cheat Sheet or Reference",
                    "title": f"OS Concepts Summary: {task_title}",
                    "url": "https://github.com/donnemartin/system-design-primer",
                    "description": f"Summary notes and reference guide for {task_title}."
                }
            ]

    # 5. Aptitude / Mathematics fallbacks
    elif any(k in t_lower for k in ["aptitude", "math", "percentage", "profit", "loss", "ratio", "permutation", "probability", "time and work", "speed"]):
        if "percentage" in t_lower:
            return [
                {
                    "category": "High-quality Free Tutorial / Article",
                    "title": "IndiaBIX: Percentage Formulas & Concepts",
                    "url": "https://www.indiabix.com/aptitude/percentage/",
                    "description": "Essential percentage formulas, shortcut tricks, and solved examples."
                },
                {
                    "category": "Official Documentation",
                    "title": "GeeksforGeeks Aptitude: Percentage Guide",
                    "url": "https://www.geeksforgeeks.org/percentage-aptitude-questions-and-answers/",
                    "description": "Structured quantitative aptitude guide covering percentage calculations."
                },
                {
                    "category": "Free YouTube Video",
                    "title": "Khan Academy / FeelFreeToLearn: Percentages Video",
                    "url": f"https://www.youtube.com/results?search_query=percentages+aptitude+tricks",
                    "description": "Visual breakdown of percentage calculation shortcuts and problem solving."
                },
                {
                    "category": "Interactive Practice Platform",
                    "title": "IndiaBIX: Percentage Practice Questions & Tests",
                    "url": "https://www.indiabix.com/aptitude/percentage/001001",
                    "description": "Interactive multiple choice practice problems with step-by-step solutions."
                },
                {
                    "category": "Cheat Sheet or Reference",
                    "title": "Aptitude Percentage Fraction Conversion Table",
                    "url": "https://www.geeksforgeeks.org/quantitative-aptitude/",
                    "description": "Quick reference conversion chart for fractions to percentages."
                }
            ]
        else:
            return [
                {
                    "category": "High-quality Free Tutorial / Article",
                    "title": f"IndiaBIX: {task_title} Guide",
                    "url": f"https://www.indiabix.com/aptitude/{encoded_task}/",
                    "description": f"Formulas, concept explanations, and solved examples for {task_title}."
                },
                {
                    "category": "Official Documentation",
                    "title": f"GeeksforGeeks Aptitude: {task_title}",
                    "url": f"https://www.geeksforgeeks.org/search/?q={encoded_task}+aptitude",
                    "description": f"Step-by-step quantitative aptitude guide for {task_title}."
                },
                {
                    "category": "Free YouTube Video",
                    "title": f"Aptitude Tricks: {task_title} Video Lesson",
                    "url": f"https://www.youtube.com/results?search_query={encoded_task}+aptitude+tricks",
                    "description": f"Video tutorial featuring shortcut techniques for {task_title}."
                },
                {
                    "category": "Interactive Practice Platform",
                    "title": f"IndiaBIX Practice: {task_title} Test Set",
                    "url": f"https://www.indiabix.com/aptitude/",
                    "description": f"Interactive practice questions and timed quizzes for {task_title}."
                },
                {
                    "category": "Cheat Sheet or Reference",
                    "title": f"Aptitude Quick Formulas: {task_title}",
                    "url": "https://www.geeksforgeeks.org/quantitative-aptitude/",
                    "description": f"Quick formula cheat sheet for {task_title}."
                }
            ]

    # Universal fallback for any other task
    return [
        {
            "category": "Official Documentation",
            "title": f"Official {topic_str} Documentation: {task_title}",
            "url": f"https://www.google.com/search?q={encoded_query}+official+documentation",
            "description": f"Official reference manual and syntax specifications for studying {task_title}."
        },
        {
            "category": "High-quality Free Tutorial / Article",
            "title": f"GeeksforGeeks & FreeCodeCamp: {task_title} Tutorial",
            "url": f"https://www.geeksforgeeks.org/search/?q={encoded_query}",
            "description": f"Step-by-step free tutorial explaining core concepts of {task_title}."
        },
        {
            "category": "Free YouTube Video",
            "title": f"freeCodeCamp & YouTube Video Explanation: {task_title}",
            "url": f"https://www.youtube.com/results?search_query={encoded_query}+tutorial",
            "description": f"High-quality video lesson demonstrating practical implementation of {task_title}."
        },
        {
            "category": "Interactive Practice Platform",
            "title": f"Interactive Exercises & Practice: {task_title}",
            "url": f"https://leetcode.com/problemset/all/?search={encoded_task}",
            "description": f"Hands-on exercises and practice problems to solidify knowledge of {task_title}."
        },
        {
            "category": "Cheat Sheet or Reference",
            "title": f"Awesome {topic_str} Notes & Cheat Sheet: {task_title}",
            "url": f"https://github.com/search?q={encoded_task}+cheat+sheet",
            "description": f"Community reference guide and quick cheat sheet for {task_title}."
        }
    ]


def recommend_resources(
    task_title: str,
    topic_title: Optional[str] = "General Study",
    subject: Optional[str] = None,
    subtopic: Optional[str] = None,
    difficulty: Optional[str] = "Beginner",
    learning_objective: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generates and caches free, high-quality, beginner-friendly learning resources 
    STRICTLY tailored to the current study task, ensuring zero roadmap/career plan clutter.
    """
    t_clean = task_title.strip()
    top_clean = (topic_title or "General").strip()
    sub_clean = (subject or top_clean).strip()
    subtop_clean = (subtopic or "").strip()
    diff_clean = (difficulty or "Beginner").strip()

    cache_key = f"{sub_clean.lower()}||{top_clean.lower()}||{subtop_clean.lower()}||{t_clean.lower()}||{diff_clean.lower()}"

    if cache_key in _RESOURCE_CACHE:
        logger.info(f"Returning in-memory cached task resources for '{t_clean}'")
        return _RESOURCE_CACHE[cache_key]

    try:
        ai_service = get_ai_service()
        system_instruction = (
            "You are an expert developer coach and resource recommendation engine. "
            "Your sole objective is to answer: 'What are the best free resources to learn THIS SPECIFIC STUDY TASK?'\n\n"
            "STRICT RULES:\n"
            "1. Focus ONLY on the specific study task. DO NOT recommend entire roadmaps, career paths, learning plans, or study plans.\n"
            "2. The words 'roadmap', 'career path', 'learning plan', and 'study plan' MUST NEVER appear in your response titles, URLs, or descriptions.\n"
            "3. Return resources strictly in this priority order:\n"
            "   1. Official Documentation (if applicable)\n"
            "   2. High-quality Free Tutorial / Article\n"
            "   3. Free YouTube Video\n"
            "   4. Interactive Practice Platform\n"
            "   5. Coding Practice / Problems (only if applicable)\n"
            "   6. Cheat Sheet or Reference (optional)\n"
            "4. Only recommend free, high-quality, relevant resources matching the difficulty level."
        )

        prompt_lines = [
            f"Subject: {sub_clean}",
            f"Topic: {top_clean}",
        ]
        if subtop_clean:
            prompt_lines.append(f"Subtopic: {subtop_clean}")
        prompt_lines.append(f"Task: {t_clean}")
        prompt_lines.append(f"Difficulty: {diff_clean}")
        if learning_objective:
            prompt_lines.append(f"Learning Objective: {learning_objective}")

        prompt_lines.extend([
            "",
            "Provide JSON with this exact schema:",
            "{",
            f'  "task": "{t_clean}",',
            '  "resources": [',
            '    {"category": "Official Documentation", "title": "...", "url": "...", "description": "..."}',
            '  ]',
            "}"
        ])

        prompt = "\n".join(prompt_lines)

        schema = {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "resources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "description": {"type": "string"}
                        },
                        "required": ["category", "title", "url", "description"]
                    }
                }
            },
            "required": ["task", "resources"]
        }

        res_json = ai_service.generate_json(prompt, response_schema=schema, system_instruction=system_instruction)
        raw_list = res_json.get("resources", [])
        
        cleaned = clean_and_validate_resources(raw_list, t_clean)

        if len(cleaned) >= 3:
            _RESOURCE_CACHE[cache_key] = cleaned[:6]
            return cleaned[:6]

    except Exception as e:
        logger.warning(f"AI Resource Generation exception, falling back to curated resources: {e}")

    fallback = get_fallback_resources(
        task_title=t_clean,
        topic_title=top_clean,
        subject=sub_clean,
        difficulty=diff_clean
    )
    cleaned_fallback = clean_and_validate_resources(fallback, t_clean)
    _RESOURCE_CACHE[cache_key] = cleaned_fallback
    return cleaned_fallback

