# Import all models so they register on Base.metadata
from app.database.base_class import Base  # noqa
from app.models.core import Users, Settings, Timetable, Holidays, Events, Notifications, Analytics, Reports  # noqa
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks, DailyPlans, StudySessions, Progress, Resources, RevisionHistory, UserOverrides  # noqa
