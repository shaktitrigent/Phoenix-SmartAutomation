"""
Phoenix Enterprise QA Automation Platform (Core)

Client-side SDK + CLI for deterministic test generation and execution.
All AI/MCP reasoning is delegated to phoenix-intelligence.
"""

__version__ = "0.1.0"

__all__ = ["PhoenixClient"]


def __getattr__(name: str):
    """Keep lightweight submodules importable without loading SDK/database deps."""
    if name == "PhoenixClient":
        from phoenix.sdk.client import PhoenixClient

        return PhoenixClient
    raise AttributeError(name)
