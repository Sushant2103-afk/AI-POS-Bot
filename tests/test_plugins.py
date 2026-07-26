import os
from app.core.plugins import BasePlugin, PluginManager

def test_plugin_discovery():
    """
    Verify that the PluginManager correctly scans and registers the default placement_coach plugin.
    """
    pm = PluginManager()
    pm.discover_and_load_plugins()
    
    plugin = pm.get_plugin("placement_coach")
    assert plugin is not None
    assert plugin.name == "placement_coach"
    assert plugin.version == "1.0.0"
    assert "placement_coach" in [p.name for p in pm.get_all_plugins()]

def test_custom_plugin_registration(mocker):
    """
    Verify that plugin lifecycle methods can be registered and called successfully.
    """
    pm = PluginManager()
    
    class TestMockPlugin(BasePlugin):
        name = "test_mock_plugin"
        description = "Mock plugin for verification"
        version = "0.1.0"
        
    plugin = TestMockPlugin()
    pm.plugins[plugin.name] = plugin
    
    spy_routes = mocker.spy(plugin, "register_routes")
    spy_models = mocker.spy(plugin, "register_models")
    spy_ui = mocker.spy(plugin, "register_ui")
    
    # Call hooks
    dummy_app = "FastAPIInstance"
    plugin.register_routes(dummy_app)
    plugin.register_models()
    plugin.register_ui()
    
    assert spy_routes.call_count == 1
    assert spy_models.call_count == 1
    assert spy_ui.call_count == 1
