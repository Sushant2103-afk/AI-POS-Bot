import streamlit as st
import datetime
import os
import pandas as pd
from sqlalchemy.orm import Session

from app.models.core import Users, Settings, Timetable
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks, StudySessions, DailyPlans, Progress, RevisionHistory
from app.imports.engine import ImportEngine
from app.exports.engine import ExportEngine
from app.planner.service import PlannerService
from app.planner.spaced_repetition import SpacedRepetitionEngine
from app.ai.service import get_ai_service
from app.core.config import settings

# --- Tab 1: Setup Wizard & Ingestion ---
def render_setup_wizard(db: Session, user_id: int):
    st.markdown("<h2 class='glow-title'>⚙️ Setup Wizard & Curriculum Import</h2>", unsafe_allow_html=True)
    
    # 1. User Profile Setup
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        st.error("User not found.")
        return
        
    break_setting = db.query(Settings).filter(Settings.user_id == user_id, Settings.key == "break_duration_minutes").first()
    break_val = int(break_setting.value) if break_setting else settings.user_profile.break_duration_minutes

    st.subheader("👤 User Profile Settings")
    with st.form("profile_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Name", value=user.name)
            email = st.text_input("Email", value=user.email or "")
        with col2:
            wake_up = st.text_input("Wake Up Time (HH:MM)", value=user.wake_up_time or "07:00")
            sleep = st.text_input("Sleep Time (HH:MM)", value=user.sleep_time or "23:00")
            
        col3, col4 = st.columns(2)
        with col3:
            study_hours = st.number_input("Preferred Daily Study Hours", min_value=1.0, max_value=16.0, value=float(user.preferred_study_hours or 6.0), step=0.5)
        with col4:
            break_min = st.number_input("Break Duration (minutes)", min_value=5, max_value=60, value=int(break_val))
            
        if st.form_submit_button("Save Profile Settings", use_container_width=True):
            user.name = name
            user.email = email if email else None
            user.wake_up_time = wake_up
            user.sleep_time = sleep
            user.preferred_study_hours = study_hours
            
            if break_setting:
                break_setting.value = str(break_min)
            else:
                db.add(Settings(user_id=user_id, key="break_duration_minutes", value=str(break_min)))
                
            db.commit()
            st.success("✅ Profile settings saved successfully!")
            st.rerun()

    # 2. Timetable Commitment Slots
    st.write("---")
    st.subheader("📅 Weekly Timetable Slots & Commitments")
    st.caption("Register fixed commitments (College, Gym, Meals) so the AI planner reserves those hours.")
    
    DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    
    timetable = db.query(Timetable).filter(Timetable.user_id == user_id).all()
    if timetable:
        cols = st.columns(3)
        for i, slot in enumerate(timetable):
            day_str = DAYS_OF_WEEK[slot.day_of_week] if isinstance(slot.day_of_week, int) and 0 <= slot.day_of_week < 7 else str(slot.day_of_week)
            with cols[i % 3]:
                st.markdown(
                    f"<div class='stat-box' style='border-left-color: #ef4444; margin-bottom:10px;'>"
                    f"<b>{slot.activity_name.capitalize()}</b><br>"
                    f"{day_str.capitalize()}s: {slot.start_time} - {slot.end_time}"
                    f"</div>",
                    unsafe_allow_html=True
                )
                if st.button(f"Delete Slot {slot.id}", key=f"del_{slot.id}"):
                    db.delete(slot)
                    db.commit()
                    st.success(f"Deleted slot: {slot.activity_name}")
                    st.rerun()
    else:
        st.info("No regular commitments scheduled yet.")
        
    with st.form("timetable_form"):
        st.write("➕ **Add Commitment Slot**")
        col1, col2 = st.columns(2)
        with col1:
            activity = st.text_input("Activity Name (e.g. Lectures, Gym, Lunch)")
            day = st.selectbox("Day of Week", DAYS_OF_WEEK)
        with col2:
            start_t = st.text_input("Start Time (HH:MM)", value="09:00")
            end_t = st.text_input("End Time (HH:MM)", value="10:00")
            
        if st.form_submit_button("Add Commitment", use_container_width=True):
            day_idx = DAYS_OF_WEEK.index(day.lower())
            new_slot = Timetable(
                user_id=user_id,
                day_of_week=day_idx,
                start_time=start_t,
                end_time=end_t,
                activity_name=activity
            )
            db.add(new_slot)
            db.commit()
            st.success("✅ Added timetable slot!")
            st.rerun()

    # 3. Roadmap Ingest
    st.write("---")
    st.subheader("📚 Import Roadmap Curriculum")
    
    upload_type = st.radio("Choose Ingestion Mode", ["File Upload", "Raw Text Paste"])
    
    if upload_type == "File Upload":
        uploaded_file = st.file_uploader("Upload Document (PDF, Word, Excel, Markdown, Text, CSV)", type=["pdf", "docx", "xlsx", "md", "txt", "csv"])
        if uploaded_file:
            if st.button("Parse & Ingest Document", use_container_width=True):
                os.makedirs("roadmaps", exist_ok=True)
                file_path = os.path.join("roadmaps", uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                    
                with st.spinner("Analyzing curriculum with AI Services..."):
                    try:
                        engine = ImportEngine(db)
                        roadmap = engine.import_roadmap(user_id=user_id, file_path=file_path)
                        st.success(f"🎉 Success! Imported roadmap: '{roadmap.title}' (ID: {roadmap.id})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to parse document: {e}")
    else:
        title = st.text_input("Roadmap Title", value="SDE Placement Preparation")
        raw_text = st.text_area("Paste Syllabus / Topics list here", height=200, placeholder="Month 1: Data Structures\nWeek 1: Arrays & Hashing\n- Solve 20 Leetcode problems\n- Learn Two Pointer pattern")
        if st.button("Parse Pasted Curriculum", use_container_width=True):
            if not raw_text.strip():
                st.warning("Please paste some curriculum text first.")
            else:
                with st.spinner("Structuring curriculum with AI Services..."):
                    try:
                        engine = ImportEngine(db)
                        roadmap = engine.import_roadmap_text(user_id=user_id, raw_text=raw_text, title=title)
                        st.success(f"🎉 Success! Imported roadmap: '{roadmap.title}' (ID: {roadmap.id})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to parse text: {e}")

# --- Tab 2: Scheduler & Checklist ---
def render_scheduler(db: Session, user_id: int):
    st.markdown("<h2 class='glow-title'>📅 Daily Study Planner & Rescheduling</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        target_date = st.date_input("Target Date", value=datetime.date.today())
    with col2:
        st.write("")
        st.write("")
        if st.button("🔄 Generate Today's Plan", use_container_width=True):
            with st.spinner("Calculating free slots and energy distribution..."):
                try:
                    planner = PlannerService(db)
                    plan = planner.generate_daily_plan(user_id, target_date)
                    st.success(f"Generated daily plan with {len(plan.study_sessions)} blocks!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not generate plan: {e}")
                    
    if st.button("⚠️ Reschedule Outstanding Tasks to Tomorrow", use_container_width=True):
        with st.spinner("Moving incomplete blocks..."):
            try:
                planner = PlannerService(db)
                moved_count = planner.reschedule_unfinished_tasks(user_id, target_date)
                st.success(f"✅ Successfully postponed {moved_count} uncompleted task(s) to tomorrow's queue.")
                st.rerun()
            except Exception as e:
                st.error(f"Rescheduling failed: {e}")
                
    st.write("---")
    
    plan = db.query(DailyPlans).filter(
        DailyPlans.user_id == user_id,
        DailyPlans.date == target_date
    ).first()
    
    if not plan or not plan.study_sessions:
        st.info(f"No study sessions generated for {target_date}. Click 'Generate Today's Plan' to calculate schedules.")
        return
        
    st.write(f"📝 **Schedule Checklist for {target_date}** (Available hours: {plan.total_available_hours}h)")
    
    for session in plan.study_sessions:
        card_border = "#10b981" if session.status == "completed" else "#f59e0b" if session.status == "planned" else "#ef4444"
        
        with st.container():
            st.markdown(
                f"<div class='glass-card' style='border-left: 5px solid {card_border};'>"
                f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                f"<h4>⏱️ Block {session.id}: {session.start_time} - {session.end_time}</h4>"
                f"<span class='badge-active' style='background-color:{card_border}22; color:{card_border}; border-color:{card_border}44;'>"
                f"{session.status.upper()}</span>"
                f"</div>"
                f"<b>Task:</b> {session.task.title}<br>"
                f"<b>Time needed:</b> {session.task.estimated_minutes} mins | <b>Energy:</b> {session.task.energy_level.upper()}<br>"
                f"<b>Focus Topic:</b> {session.task.topic.title}<br>"
                f"</div>",
                unsafe_allow_html=True
            )
            
            if session.status == "planned":
                if st.button(f"Mark Completed (Block {session.id})", key=f"comp_{session.id}"):
                    session.status = "completed"
                    session.task.is_completed = True
                    
                    progress = Progress(
                        task_id=session.task_id,
                        completed_at=datetime.datetime.utcnow(),
                        actual_minutes_spent=session.task.estimated_minutes,
                        notes="Completed via Streamlit Web Dashboard."
                    )
                    db.add(progress)
                    
                    rep_engine = SpacedRepetitionEngine(db)
                    rep_engine.schedule_revisions(session.task_id, target_date)
                    
                    db.commit()
                    st.success(f"🎉 Marked block {session.id} completed! Spaced revision scheduled.")
                    st.rerun()

# --- Tab 3: Analytics ---
def render_analytics(db: Session, user_id: int):
    st.markdown("<h2 class='glow-title'>📊 Analytics & Progress Dashboard</h2>", unsafe_allow_html=True)
    
    total_roadmaps = db.query(Roadmaps).filter(Roadmaps.user_id == user_id).count()
    all_tasks = db.query(Tasks).join(Topics).join(Roadmaps).filter(Roadmaps.user_id == user_id).all()
    
    total_tasks = len(all_tasks)
    completed_tasks = len([t for t in all_tasks if t.is_completed])
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0
    
    revisions_queued = db.query(RevisionHistory).join(Tasks).join(Topics).join(Roadmaps).filter(
        Roadmaps.user_id == user_id
    ).count()
    
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"<div class='stat-box'><div class='stat-value'>{total_roadmaps}</div><div class='stat-label'>Active Roadmaps</div></div>", unsafe_allow_html=True)
    with m2:
        st.markdown(f"<div class='stat-box'><div class='stat-value'>{total_tasks}</div><div class='stat-label'>Total Tasks</div></div>", unsafe_allow_html=True)
    with m3:
        st.markdown(f"<div class='stat-box'><div class='stat-value'>{completion_rate:.1f}%</div><div class='stat-label'>Completion Rate</div></div>", unsafe_allow_html=True)
    with m4:
        st.markdown(f"<div class='stat-box'><div class='stat-value'>{revisions_queued}</div><div class='stat-label'>Revisions Queued</div></div>", unsafe_allow_html=True)
        
    st.write("---")
    st.subheader("📈 7-Day Study Session Trend")
    
    today = datetime.date.today()
    dates = [today - datetime.timedelta(days=i) for i in range(6, -1, -1)]
    
    completed_counts = []
    planned_counts = []
    
    for d in dates:
        plan = db.query(DailyPlans).filter(DailyPlans.user_id == user_id, DailyPlans.date == d).first()
        if plan:
            c = sum(1 for s in plan.study_sessions if s.status == "completed")
            p = sum(1 for s in plan.study_sessions if s.status == "planned")
            completed_counts.append(c)
            planned_counts.append(p)
        else:
            completed_counts.append(0)
            planned_counts.append(0)
            
    df = pd.DataFrame({
        "Date": [d.strftime("%a (%m/%d)") for d in dates],
        "Completed Blocks": completed_counts,
        "Remaining Blocks": planned_counts
    })
    df.set_index("Date", inplace=True)
    st.bar_chart(df, height=300)

# --- Tab 4: AI Mock Interviewer ---
def render_mock_interview(db: Session, user_id: int):
    st.markdown("<h2 class='glow-title'>💬 AI Mock Technical Interviewer</h2>", unsafe_allow_html=True)
    st.write("Select a topic from your roadmap to begin an interactive AI mock technical interview.")
    
    topics = db.query(Topics).join(Roadmaps).filter(Roadmaps.user_id == user_id).all()
    if not topics:
        st.warning("Please upload a roadmap curriculum first in the Setup tab.")
        return
        
    selected_topic = st.selectbox("Select Interview Topic", [t.title for t in topics])
    
    if "messages" not in st.session_state or st.session_state.get("topic") != selected_topic:
        st.session_state.messages = []
        st.session_state.topic = selected_topic
        
        try:
            ai_service = get_ai_service()
            prompt = (
                f"You are a tech interviewer evaluating a Software Engineer candidate on '{selected_topic}'. "
                f"Ask the first technical interview question. Keep it concise, focused, and professional."
            )
            first_question = ai_service.generate_text(prompt)
            st.session_state.messages.append({"role": "assistant", "content": first_question})
        except Exception:
            st.session_state.messages.append({
                "role": "assistant", 
                "content": f"Hello! Let's start the interview on '{selected_topic}'. Can you explain the core concepts of this topic?"
            })
            
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    if user_input := st.chat_input("Type your response here..."):
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        with st.spinner("Analyzing response..."):
            try:
                ai_service = get_ai_service()
                last_question = st.session_state.messages[-2]["content"] if len(st.session_state.messages) >= 2 else "initial question"
                
                eval_prompt = (
                    f"Topic: {selected_topic}\n"
                    f"Question Asked: {last_question}\n"
                    f"Candidate Answer: {user_input}\n\n"
                    f"Evaluate the candidate's answer out of 10, provide constructive feedback, "
                    f"and ask the next technical question on '{selected_topic}'."
                )
                ai_reply = ai_service.generate_text(eval_prompt)
                
                with st.chat_message("assistant"):
                    st.markdown(ai_reply)
                st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            except Exception as e:
                st.error(f"Error communicating with AI Service: {e}")

# --- Tab 5: Export Data & Reports ---
def render_exports(db: Session, user_id: int):
    st.markdown("<h2 class='glow-title'>📤 Export Study Reports & Data</h2>", unsafe_allow_html=True)
    st.write("Download your daily schedule, task history, and analytics in Markdown, CSV, or JSON format.")
    
    target_date = st.date_input("Select Date to Export", value=datetime.date.today(), key="export_date")
    
    plan = db.query(DailyPlans).filter(
        DailyPlans.user_id == user_id,
        DailyPlans.date == target_date
    ).first()
    
    if not plan:
        st.warning(f"No daily plan found for {target_date}. Please generate a plan in the Daily Planner tab first.")
        return
        
    # Serialize plan data
    plan_dict = {
        "date": str(plan.date),
        "total_available_hours": plan.total_available_hours,
        "is_finalized": plan.is_finalized,
        "study_sessions": [
            {
                "start_time": s.start_time,
                "end_time": s.end_time,
                "status": s.status,
                "task": {
                    "title": s.task.title,
                    "estimated_minutes": s.task.estimated_minutes,
                    "priority": s.task.priority,
                    "energy_level": s.task.energy_level,
                    "is_completed": s.task.is_completed
                } if s.task else {}
            } for s in plan.study_sessions
        ]
    }
    
    col1, col2, col3 = st.columns(3)
    with col1:
        md_data = ExportEngine.export_plan_markdown(plan_dict)
        st.download_button(
            label="📄 Download Markdown Checklist",
            data=md_data,
            file_name=f"study_plan_{target_date}.md",
            mime="text/markdown",
            use_container_width=True
        )
    with col2:
        csv_data = ExportEngine.export_plan_csv(plan_dict)
        st.download_button(
            label="📊 Download CSV Spreadsheet",
            data=csv_data,
            file_name=f"study_plan_{target_date}.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col3:
        json_data = ExportEngine.export_plan_json(plan_dict)
        st.download_button(
            label="📦 Download JSON Backup",
            data=json_data,
            file_name=f"study_plan_{target_date}.json",
            mime="application/json",
            use_container_width=True
        )
    
    st.write("---")
    st.subheader("Preview Report (Markdown)")
    st.code(md_data, language="markdown")

# --- Tab 6: Multi-Roadmap Manager ---
def render_multi_roadmap_manager(db: Session, user_id: int):
    st.markdown("<h2 class='glow-title'>🗂 Multi-Roadmap Management</h2>", unsafe_allow_html=True)
    st.write("Manage, switch, pause, resume, prioritize, and duplicate your independent study roadmaps.")

    roadmaps = db.query(Roadmaps).filter(Roadmaps.user_id == user_id).order_by(Roadmaps.priority.asc(), Roadmaps.id.asc()).all()

    if not roadmaps:
        st.info("No roadmaps found. Go to the 'Setup Wizard & Curriculum Import' tab to import your first syllabus!")
        return

    for rm in roadmaps:
        st_color = "#10b981" if (rm.status == "active" or (rm.status is None and rm.is_active)) else "#f59e0b" if rm.status == "paused" else "#94a3b8"
        status_label = (rm.status or "active").upper()

        all_tasks = db.query(Tasks).join(Topics).filter(Topics.roadmap_id == rm.id).all()
        total_cnt = len(all_tasks)
        completed_cnt = len([t for t in all_tasks if t.is_completed])
        pct = (completed_cnt / total_cnt * 100.0) if total_cnt > 0 else 0.0

        with st.container():
            st.markdown(
                f"<div class='glass-card' style='border-left: 5px solid {st_color};'>"
                f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                f"<h3>📚 {rm.title} <span style='font-size:0.8rem; color:#94a3b8;'>[{rm.category or 'General'}]</span></h3>"
                f"<span class='badge-active' style='background-color:{st_color}22; color:{st_color}; border-color:{st_color}44;'>"
                f"{status_label}</span>"
                f"</div>"
                f"<b>Priority:</b> P{rm.priority or 1} | <b>Schedule:</b> {(rm.schedule_type or 'daily').capitalize()}<br>"
                f"<b>Progress:</b> {completed_cnt}/{total_cnt} tasks ({pct:.1f}%)<br>"
                f"</div>",
                unsafe_allow_html=True
            )

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                new_prio = st.number_input(f"Priority (ID {rm.id})", min_value=1, max_value=10, value=int(rm.priority or 1), key=f"prio_{rm.id}")
                if new_prio != (rm.priority or 1):
                    rm.priority = new_prio
                    db.commit()
                    st.rerun()

            with col2:
                if rm.status == "active" or (rm.status is None and rm.is_active):
                    if st.button(f"⏸ Pause #{rm.id}", key=f"pause_{rm.id}", use_container_width=True):
                        rm.status = "paused"
                        rm.is_active = False
                        db.commit()
                        st.rerun()
                else:
                    if st.button(f"▶ Resume #{rm.id}", key=f"resume_{rm.id}", use_container_width=True):
                        rm.status = "active"
                        rm.is_active = True
                        db.commit()
                        st.rerun()

            with col3:
                if st.button(f"📄 Duplicate #{rm.id}", key=f"dup_{rm.id}", use_container_width=True):
                    engine = ImportEngine(db)
                    engine.duplicate_roadmap(user_id, rm.id)
                    st.success(f"Duplicated roadmap #{rm.id}!")
                    st.rerun()

            with col4:
                if st.button(f"🗑 Delete #{rm.id}", key=f"del_rm_{rm.id}", use_container_width=True):
                    db.delete(rm)
                    db.commit()
                    st.success(f"Deleted roadmap #{rm.id}!")
                    st.rerun()

            st.write("---")
