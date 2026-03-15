# app/tools/mcp_tools.py
import warnings
from app.core.tool_registry import tool_registry

warnings.warn(
    "mcp_tools is deprecated. Use app.core.tool_registry instead.",
    DeprecationWarning,
    stacklevel=2
)

# Export for backward compatibility
mcp_server = tool_registry