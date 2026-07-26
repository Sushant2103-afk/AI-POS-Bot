import streamlit as st
import os
import sys

# Configure sys.path so app packages are discoverable
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database.session import SessionLocal
from app.models.core import Users

try:
    from app.frontend.views import (
        render_setup_wizard,
        render_scheduler,
        render_analytics,
        render_mock_interview,
        render_exports,
        render_multi_roadmap_manager
    )
except ImportError:
    from app.frontend.views import (
        render_setup_wizard,
        render_scheduler,
        render_analytics,
        render_mock_interview
    )
    def render_exports(db, user_id):
        st.info("Export data functionality loading...")
    def render_multi_roadmap_manager(db, user_id):
        st.info("Multi-roadmap manager loading...")

# 1. Setup Streamlit Page Layout
st.set_page_config(
    page_title="AI Companion - Personal Operating System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inject Custom Theme CSS Stylesheets
css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.css")
if os.path.exists(css_path):
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# 3. DB Session lifecycle hook
db = SessionLocal()

# 4. Handle Default User resolution
user_id = 1
user = db.query(Users).filter(Users.id == user_id).first()
if not user:
    user = Users(
        name="Placement Candidate", 
        email="candidate@example.com",
        wake_up_time="07:00",
        sleep_time="23:00",
        preferred_study_hours=6.0
    )
    db.add(user)
    db.commit()
    db.refresh(user)

# 5. Sidebar Branding & Custom Navigation Tabs
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #818cf8;'>🤖 AI Companion</h2>", unsafe_allow_html=True)
    st.markdown("<div style='text-align: center; color: #94a3b8; font-size: 0.9rem; margin-bottom: 15px;'>Personal Operating System</div>", unsafe_allow_html=True)
    st.write(f"Logged in as: **{user.name}**")
    st.write("---")
    
    page = st.radio(
        "Navigation Menu",
        [
            "🏠 Home & Setup Wizard",
            "🗂 Multi-Roadmaps",
            "📅 Daily Planner",
            "📊 Progress & Analytics",
            "💬 AI Mock Interview",
            "📤 Export Data & Reports"
        ]
    )
    
    st.write("---")
    st.markdown(
        "<div style='text-align: center; color: #64748b; font-size: 0.8rem;'>"
        "AI Personal Operating System<br>v1.2.0 • Production Ready"
        "</div>",
        unsafe_allow_html=True
    )

# 6. Render selected view content
try:
    if "Home" in page:
        render_setup_wizard(db, user.id)
    elif "Roadmaps" in page:
        render_multi_roadmap_manager(db, user.id)
    elif "Planner" in page:
        render_scheduler(db, user.id)
    elif "Analytics" in page:
        render_analytics(db, user.id)
    elif "Mock Interview" in page:
        render_mock_interview(db, user.id)
    elif "Export" in page:
        render_exports(db, user.id)
finally:
    db.close()
