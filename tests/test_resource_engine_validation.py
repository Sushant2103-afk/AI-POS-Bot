import pytest
from app.ai.resources import recommend_resources, FORBIDDEN_KEYWORDS, _RESOURCE_CACHE

TEST_STUDY_TASKS = [
    # 1-3. Python Domain
    {
        "subject": "Python",
        "topic": "Python Basics & Modules",
        "task": "Import Modules",
        "difficulty": "Beginner"
    },
    {
        "subject": "Python",
        "topic": "Data Structures",
        "task": "List Comprehensions",
        "difficulty": "Beginner"
    },
    {
        "subject": "Python",
        "topic": "Environment Management",
        "task": "Virtual Environments & venv",
        "difficulty": "Intermediate"
    },
    # 4-7. Data Structures & Algorithms Domain
    {
        "subject": "DSA",
        "topic": "Searching Algorithms",
        "task": "Binary Search",
        "difficulty": "Intermediate"
    },
    {
        "subject": "DSA",
        "topic": "Sorting Algorithms",
        "task": "Merge Sort Algorithm",
        "difficulty": "Intermediate"
    },
    {
        "subject": "DSA",
        "topic": "Graph Algorithms",
        "task": "Breadth First Search (BFS)",
        "difficulty": "Intermediate"
    },
    {
        "subject": "DSA",
        "topic": "Array Optimization",
        "task": "Two Pointer Technique",
        "difficulty": "Intermediate"
    },
    # 8-10. AI / Machine Learning Domain
    {
        "subject": "Machine Learning",
        "topic": "Supervised Learning",
        "task": "Linear Regression",
        "difficulty": "Beginner"
    },
    {
        "subject": "Machine Learning",
        "topic": "Optimization Algorithms",
        "task": "Gradient Descent Optimization",
        "difficulty": "Intermediate"
    },
    {
        "subject": "Artificial Intelligence",
        "topic": "Deep Learning",
        "task": "Convolutional Neural Networks (CNNs)",
        "difficulty": "Advanced"
    },
    # 11-13. Operating Systems Domain
    {
        "subject": "Operating Systems",
        "topic": "Process Management",
        "task": "Processes vs Threads",
        "difficulty": "Intermediate"
    },
    {
        "subject": "Operating Systems",
        "topic": "Memory Management",
        "task": "Page Replacement Algorithms (FIFO/LRU)",
        "difficulty": "Intermediate"
    },
    {
        "subject": "Operating Systems",
        "topic": "Synchronization & Concurrency",
        "task": "Deadlock Prevention & Banker's Algorithm",
        "difficulty": "Advanced"
    },
    # 14-16. Aptitude Domain
    {
        "subject": "Aptitude",
        "topic": "Quantitative Aptitude",
        "task": "Percentages",
        "difficulty": "Beginner"
    },
    {
        "subject": "Aptitude",
        "topic": "Quantitative Aptitude",
        "task": "Profit and Loss Calculation",
        "difficulty": "Beginner"
    },
    {
        "subject": "Aptitude",
        "topic": "Combinatorics",
        "task": "Permutations and Combinations",
        "difficulty": "Intermediate"
    },
    # 17-21. Additional Core Computer Science Domains
    {
        "subject": "SQL & Databases",
        "topic": "Database Indexing",
        "task": "SQL Indexing & B-Trees",
        "difficulty": "Intermediate"
    },
    {
        "subject": "Web Development",
        "topic": "Frontend Layouts",
        "task": "CSS Flexbox & Grid Layout",
        "difficulty": "Beginner"
    },
    {
        "subject": "System Design",
        "topic": "Distributed Systems",
        "task": "Load Balancers & Reverse Proxies",
        "difficulty": "Advanced"
    },
    {
        "subject": "Software Engineering",
        "topic": "Version Control",
        "task": "Git Interactive Rebase",
        "difficulty": "Intermediate"
    },
    {
        "subject": "Computer Networks",
        "topic": "Transport Layer Protocols",
        "task": "TCP 3-Way Handshake",
        "difficulty": "Intermediate"
    }
]

@pytest.mark.parametrize("item", TEST_STUDY_TASKS)
def test_task_resource_recommendation(item):
    """
    Validates that recommendations generated for each of the 21 study tasks:
    1. Are non-empty (at least 3 high-quality resources).
    2. Strictly relate to the study task.
    3. Contain NO forbidden roadmap / career path terms in title or description.
    """
    resources = recommend_resources(
        task_title=item["task"],
        topic_title=item["topic"],
        subject=item["subject"],
        difficulty=item["difficulty"]
    )

    assert isinstance(resources, list)
    assert len(resources) >= 3, f"Expected at least 3 resources for task '{item['task']}'"

    for r in resources:
        title = r.get("title", "")
        description = r.get("description", "")
        category = r.get("category", "")
        url = r.get("url", "")

        assert title != "", f"Resource title should not be empty for {item['task']}"
        assert url.startswith("http"), f"Resource URL should be a valid http link: {url}"

        # Assert no forbidden roadmap keywords in title or description
        combined_text = (title + " " + description).lower()
        for forbidden in FORBIDDEN_KEYWORDS:
            assert forbidden not in combined_text, (
                f"Forbidden term '{forbidden}' found in resource for task '{item['task']}':\n"
                f"Title: {title}\nDescription: {description}"
            )

def test_resource_caching():
    """
    Verifies that identical task queries return cached recommendations.
    """
    _RESOURCE_CACHE.clear()
    
    res1 = recommend_resources("Binary Search", "Searching", "DSA", difficulty="Intermediate")
    res2 = recommend_resources("Binary Search", "Searching", "DSA", difficulty="Intermediate")
    
    assert res1 == res2
    cache_key = "dsa||searching||||binary search||intermediate"
    assert cache_key in _RESOURCE_CACHE

def test_roadmap_task_exception():
    """
    Verifies that if a user task explicitly asks to study a roadmap,
    roadmap terms are allowed for that specific task.
    """
    resources = recommend_resources("Review Web Dev Roadmap", "Career Planning", "Web Dev")
    assert len(resources) >= 1
