"""Versioned prompt loader.

Prompts live as Markdown files under ``prompts/<agent>/<version>.md`` with
YAML front-matter that declares metadata:

    ---
    name: test_generator
    version: "1.2"
    description: Generates manual and automation test cases from a user story
    agent: test_generator
    ---

    <system prompt body here>

Usage
-----
    loader = PromptLoader()
    system_prompt = loader.get("test_generator")          # latest version
    system_prompt = loader.get("test_generator", "1.1")   # pinned version
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class PromptLoader:
    """Loads versioned prompt files from disk."""

    def __init__(self, prompts_dir: Optional[str | Path] = None) -> None:
        if prompts_dir is None:
            prompts_dir = Path(__file__).resolve().parents[2] / "prompts"
        self._root = Path(prompts_dir)
        self._cache: Dict[str, Dict[str, str]] = {}  # {agent: {version: body}}

    # ------------------------------------------------------------------
    def get(self, agent: str, version: Optional[str] = None) -> str:
        """Return the prompt body for *agent* at *version* (default: latest).

        Raises FileNotFoundError if no prompt file is found.
        """
        agent_prompts = self._load_agent(agent)
        if not agent_prompts:
            raise FileNotFoundError(
                f"No prompt files found for agent '{agent}' in {self._root / agent}"
            )
        if version is None:
            version = self._latest_version(agent_prompts)
        if version not in agent_prompts:
            raise KeyError(
                f"Prompt version '{version}' not found for agent '{agent}'. "
                f"Available: {sorted(agent_prompts.keys())}"
            )
        return agent_prompts[version]

    def list_versions(self, agent: str) -> list[str]:
        """Return all available versions for *agent* sorted ascending."""
        return sorted(self._load_agent(agent).keys())

    # ------------------------------------------------------------------
    def _load_agent(self, agent: str) -> Dict[str, str]:
        if agent not in self._cache:
            self._cache[agent] = {}
            agent_dir = self._root / agent
            if not agent_dir.exists():
                logger.debug("Prompt directory not found: %s", agent_dir)
                return self._cache[agent]
            for path in sorted(agent_dir.glob("*.md")):
                try:
                    version, body = self._parse_prompt_file(path)
                    self._cache[agent][version] = body
                    logger.debug("Loaded prompt %s v%s from %s", agent, version, path)
                except Exception as exc:
                    logger.warning("Failed to parse prompt file %s: %s", path, exc)
        return self._cache[agent]

    @staticmethod
    def _parse_prompt_file(path: Path) -> tuple[str, str]:
        """Return (version, body) from a prompt Markdown file."""
        raw = path.read_text(encoding="utf-8")
        match = _FRONT_MATTER_RE.match(raw)
        if match:
            import yaml

            meta = yaml.safe_load(match.group(1)) or {}
            version = str(meta.get("version", path.stem))
            body = raw[match.end():].strip()
        else:
            version = path.stem
            body = raw.strip()
        return version, body

    @staticmethod
    def _latest_version(versions: Dict[str, str]) -> str:
        """Return the semantically latest version key."""
        def _key(v: str):
            parts = re.split(r"[.\-]", v)
            return tuple(int(p) if p.isdigit() else p for p in parts)

        return max(versions.keys(), key=_key)
