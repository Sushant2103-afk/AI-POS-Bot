import os
import importlib
from typing import Dict, List, Type
from app.core.logging import logger

class BasePlugin:
    """
    Base class for all plugins in the AI Personal Operating System.
    Future modules (Semester, Habit, Finance) must subclass this.
    """
    name: str = "base_plugin"
    description: str = "Base plugin class description"
    version: str = "1.0.0"

    def __init__(self):
        self.logger = logger.getChild(f"plugins.{self.name}")

    def register_routes(self, app) -> None:
        """
        Mount custom FastAPI routers.
        """
        self.logger.info(f"Registering API routes for plugin: {self.name}")

    def register_models(self) -> None:
        """
        Register plugin-specific SQLAlchemy database models.
        """
        self.logger.info(f"Registering database models for plugin: {self.name}")

    def register_ui(self) -> None:
        """
        Expose callbacks/widgets to render inside the Streamlit frontend.
        """
        self.logger.info(f"Registering Streamlit UI layouts for plugin: {self.name}")

class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}

    def discover_and_load_plugins(self, plugins_dir: str = None) -> None:
        """
        Dynamically scan the app/plugins folder, import modules, 
        and instantiate subclasses of BasePlugin.
        """
        if plugins_dir is None:
            current_dir = os.path.dirname(os.path.dirname(__file__))
            plugins_dir = os.path.join(current_dir, "plugins")

        if not os.path.exists(plugins_dir):
            logger.warning(f"Plugins directory not found at {plugins_dir}")
            return

        for item in os.listdir(plugins_dir):
            item_path = os.path.join(plugins_dir, item)
            if os.path.isdir(item_path):
                init_file = os.path.join(item_path, "__init__.py")
                if os.path.exists(init_file):
                    try:
                        module_name = f"app.plugins.{item}"
                        module = importlib.import_module(module_name)
                        
                        # Inspect the imported module for classes inheriting from BasePlugin
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (
                                isinstance(attr, type)
                                and issubclass(attr, BasePlugin)
                                and attr is not BasePlugin
                            ):
                                plugin_instance = attr()
                                self.plugins[plugin_instance.name] = plugin_instance
                                logger.info(f"Successfully loaded plugin: '{plugin_instance.name}' [v{plugin_instance.version}]")
                    except Exception as e:
                        logger.error(f"Error loading plugin package '{item}': {e}")

    def get_plugin(self, name: str) -> BasePlugin:
        return self.plugins.get(name)

    def get_all_plugins(self) -> List[BasePlugin]:
        return list(self.plugins.values())

plugin_manager = PluginManager()
