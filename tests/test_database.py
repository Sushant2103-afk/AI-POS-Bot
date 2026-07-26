from app.models.core import Users, Settings
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks

def test_create_user(db_session):
    """
    Test user creation and query defaults.
    """
    user = Users(
        name="Alice",
        email="alice@example.com",
        wake_up_time="06:00",
        sleep_time="22:00"
    )
    db_session.add(user)
    db_session.commit()

    queried_user = db_session.query(Users).filter(Users.email == "alice@example.com").first()
    assert queried_user is not None
    assert queried_user.name == "Alice"
    assert queried_user.preferred_study_hours == 6.0

def test_user_relations_and_cascade(db_session):
    """
    Verify complex relationship mapping and foreign key cascade deletion logic.
    """
    # Create user
    user = Users(name="Bob", email="bob@example.com")
    db_session.add(user)
    db_session.flush()

    # Create setting
    setting = Settings(user_id=user.id, key="theme", value="light")
    db_session.add(setting)

    # Create roadmap
    roadmap = Roadmaps(user_id=user.id, title="Bob Roadmap")
    db_session.add(roadmap)
    db_session.flush()

    # Create Month
    month = Months(roadmap_id=roadmap.id, month_number=1, title="Month 1")
    db_session.add(month)
    db_session.flush()

    # Create Week
    week = Weeks(month_id=month.id, week_number=1, title="Week 1")
    db_session.add(week)
    db_session.flush()

    # Create Topic
    topic = Topics(roadmap_id=roadmap.id, week_id=week.id, title="Recursion")
    db_session.add(topic)
    db_session.flush()

    # Create Task
    task = Tasks(topic_id=topic.id, title="Factorial recursion")
    db_session.add(task)
    
    db_session.commit()

    # Assert relations are set up
    assert db_session.query(Settings).filter(Settings.user_id == user.id).count() == 1
    assert db_session.query(Roadmaps).filter(Roadmaps.user_id == user.id).count() == 1
    assert db_session.query(Tasks).filter(Tasks.topic_id == topic.id).count() == 1

    # Execute cascade delete on user
    db_session.delete(user)
    db_session.commit()

    # Verify that dependent records have been automatically deleted
    assert db_session.query(Settings).filter(Settings.user_id == user.id).count() == 0
    assert db_session.query(Roadmaps).filter(Roadmaps.user_id == user.id).count() == 0
