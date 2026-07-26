from app.core.plugins import BasePlugin

class PlacementCoachPlugin(BasePlugin):
    name = "placement_coach"
    description = "AI Placement Coach module for tracking placement roadmaps and mock interviews."
    version = "1.0.0"

    def register_routes(self, app) -> None:
        super().register_routes(app)
        # Placeholder for routing registration in Sprint 4

    def register_models(self) -> None:
        super().register_models()
        # Custom DB models for placement coach (if any) can be registered here in future sprints

    def register_ui(self) -> None:
        super().register_ui()
        # Streamlit layout configuration hook for Sprint 5
