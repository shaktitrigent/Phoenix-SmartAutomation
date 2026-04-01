"""LLMClient — thin wrapper kept for backwards compatibility.

New code should use LLMRouter directly.  This module re-exports LLMRouter as
LLMClient so existing call-sites (server.py, agents) keep working unchanged.
"""

from services.llm.router import LLMRouter as LLMClient

__all__ = ["LLMClient"]
