import os
import sys
from datetime import datetime, date, timedelta

# Configure sys.path so scripts folder execution can resolve the main app packages
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.session import engine, SessionLocal
from app.database.base import Base
from app.models.core import Users, Settings, Timetable, Holidays, Events, Notifications, Analytics, Reports
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks, DailyPlans, StudySessions, Progress, Resources, RevisionHistory, UserOverrides

def init_db():
    print("Connecting to the database engine and generating tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized successfully.")

    db = SessionLocal()
    try:
        # Check for existing seed data to prevent duplicate inserts
        user = db.query(Users).filter(Users.email == "student@example.com").first()
        if user:
            print("Database already contains seed data. Exiting init script.")
            return

        print("Seeding application mockup data for local development...")
        
        # 1. Create a core User
        user = Users(
            name="John Doe",
            email="student@example.com",
            wake_up_time="07:00",
            sleep_time="23:00",
            preferred_study_hours=6.0,
            timezone="UTC"
        )
        db.add(user)
        db.flush()  # Hydrate model primary key IDs

        # 2. Settings Configs
        settings_entries = [
            Settings(user_id=user.id, key="theme", value="dark"),
            Settings(user_id=user.id, key="notifications_enabled", value="true"),
            Settings(user_id=user.id, key="default_model", value="llama3-8b-8192"),
        ]
        db.add_all(settings_entries)

        # 3. Weekly recurring Timetable
        timetable_entries = [
            Timetable(user_id=user.id, day_of_week=0, activity_name="OS Lecture", start_time="09:00", end_time="10:30"),
            Timetable(user_id=user.id, day_of_week=0, activity_name="Database Systems Lab", start_time="14:00", end_time="16:00"),
            Timetable(user_id=user.id, day_of_week=2, activity_name="Computer Networks Lecture", start_time="11:00", end_time="12:30"),
            Timetable(user_id=user.id, day_of_week=4, activity_name="Placement Strategy Seminar", start_time="15:00", end_time="17:00"),
        ]
        db.add_all(timetable_entries)

        # 4. Holidays
        holidays_entries = [
            Holidays(user_id=user.id, date=date.today() + timedelta(days=12), description="Independence Day Break"),
            Holidays(user_id=user.id, date=date.today() + timedelta(days=24), description="University Technical Fest"),
        ]
        db.add_all(holidays_entries)

        # 5. One-off Events
        events_entries = [
            Events(
                user_id=user.id,
                title="DSA Mid-term Exam",
                description="Syllabus covers stacks, queues, trees and binary search algorithms.",
                start_time=datetime.now() + timedelta(days=4),
                end_time=datetime.now() + timedelta(days=4, hours=3),
                is_blocked_time=True
            ),
            Events(
                user_id=user.id,
                title="Mock Hackathon Practice",
                description="Team coding practice event organized by the development club.",
                start_time=datetime.now() + timedelta(days=14),
                end_time=datetime.now() + timedelta(days=14, hours=6),
                is_blocked_time=True
            ),
        ]
        db.add_all(events_entries)

        # 6. Roadmaps
        roadmap = Roadmaps(
            user_id=user.id,
            title="SDE Preparation Plan",
            description="Dynamic, three-month preparation plan focusing on DSA and system core concepts.",
            is_active=True
        )
        db.add(roadmap)
        db.flush()

        # 7. Months
        month1 = Months(roadmap_id=roadmap.id, month_number=1, title="Algorithm Essentials & Data Structures", target_hours=120.0)
        db.add(month1)
        db.flush()

        # 8. Weeks
        week1 = Weeks(month_id=month1.id, week_number=1, title="Arrays, HashMaps & Complexity Analysis", target_hours=30.0)
        week2 = Weeks(month_id=month1.id, week_number=2, title="Two Pointers, Sliding Windows & Stacks", target_hours=30.0)
        db.add_all([week1, week2])
        db.flush()

        # 9. Topics
        topic1 = Topics(
            roadmap_id=roadmap.id,
            week_id=week1.id,
            title="Hashing Algorithms",
            description="Techniques utilizing dictionaries and key lookups.",
            priority="high",
            estimated_hours=12.0,
            energy_level="high"
        )
        topic2 = Topics(
            roadmap_id=roadmap.id,
            week_id=week1.id,
            title="Structured Query Language (SQL)",
            description="Joins, index structures, queries optimization.",
            priority="medium",
            estimated_hours=6.0,
            energy_level="low"
        )
        db.add_all([topic1, topic2])
        db.flush()

        # 10. Tasks
        task1 = Tasks(
            topic_id=topic1.id,
            title="Solve Two Sum (LeetCode 1)",
            description="Solve using dictionary in linear complexity.",
            estimated_minutes=30,
            priority="high",
            energy_level="high",
            is_completed=False
        )
        task2 = Tasks(
            topic_id=topic1.id,
            title="Solve Valid Anagram (LeetCode 242)",
            description="Implement standard character occurrence counts comparison.",
            estimated_minutes=20,
            priority="medium",
            energy_level="low",
            is_completed=False
        )
        task3 = Tasks(
            topic_id=topic2.id,
            title="Write Complex JOIN Queries",
            description="Exercise queries on self-joins and subqueries.",
            estimated_minutes=45,
            priority="medium",
            energy_level="low",
            is_completed=False
        )
        db.add_all([task1, task2, task3])
        db.flush()

        # 11. Resources
        resource_entries = [
            Resources(topic_id=topic1.id, title="NeetCode 150 - Hashing Guide", url="https://neetcode.io/practice", resource_type="leetcode"),
            Resources(topic_id=topic2.id, title="SQL Indexing and Optimizations", url="https://use-the-index-luke.com", resource_type="documentation"),
        ]
        db.add_all(resource_entries)

        # 12. Mock Notification (sent check)
        notification = Notifications(
            user_id=user.id,
            title="Welcome to AI-POS!",
            message="Your placement roadmap has been loaded and initialized. Let's study!",
            sent_at=datetime.now(),
            provider="telegram",
            status="sent"
        )
        db.add(notification)

        # 13. Mock Analytics records for yesterday and today
        analytics_entries = [
            Analytics(
                user_id=user.id,
                metric_date=date.today() - timedelta(days=1),
                study_hours_completed=4.5,
                tasks_completed_count=2,
                tasks_total_count=3,
                streak_count=1,
                readiness_score=15.0
            ),
            Analytics(
                user_id=user.id,
                metric_date=date.today(),
                study_hours_completed=0.0,
                tasks_completed_count=0,
                tasks_total_count=3,
                streak_count=2,
                readiness_score=16.0
            ),
        ]
        db.add_all(analytics_entries)

        # 14. Mock Weekly Report
        report = Reports(
            user_id=user.id,
            report_type="weekly",
            generated_at=datetime.now(),
            content="### Weekly Progress Summary\n- Total study hours: 4.5\n- Tasks completed: 2/3\n- Performance is on track.",
            file_path=None
        )
        db.add(report)

        db.commit()
        print("Database seeded successfully with all 19 schemas fully populated!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
