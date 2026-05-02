"""Hermes plugin loader for Jackrabbit Crypto Plugin."""
from pathlib import Path
import sys
import logging

logger = logging.getLogger(__name__)

# Add parent dir to path so crypto_plugin can import its deps
plugin_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(plugin_dir))
sys.path.insert(0, '/opt/hermes-crypto')

from crypto_plugin import CryptoPlugin, create_plugin_instance


def register(ctx):
    """Register crypto plugin hooks with Hermes Agent.

    Maps plugin methods to the current Hermes hook API.
    Note: The class method is still named on_tool_result for backward
    compatibility, but it is registered under the post_tool_call hook
    which replaced the deprecated on_tool_result hook.
    """
    plugin = create_plugin_instance()

    if hasattr(plugin, 'on_session_start'):
        ctx.register_hook('on_session_start', plugin.on_session_start)
    if hasattr(plugin, 'on_tool_result'):
        ctx.register_hook('post_tool_call', plugin.on_tool_result)
    if hasattr(plugin, 'on_session_end'):
        ctx.register_hook('on_session_end', plugin.on_session_end)

    logger.info("Jackrabbit crypto plugin registered")


__all__ = ['CryptoPlugin', 'create_plugin_instance', 'register']
