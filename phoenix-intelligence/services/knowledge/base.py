"""Knowledge base manager"""

import logging
import json
import re
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeEntry:
    """Knowledge entry"""

    title: str
    content: str
    category: str
    tags: List[str]
    metadata: Dict[str, Any]


class KnowledgeBase:
    """Knowledge base manager for agents"""

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize knowledge base.

        Args:
            base_path: Base path to knowledge base directory. If None, uses default.
        """
        if base_path is None:
            # Default to phoenix/knowledge directory
            base_path = Path(__file__).parent

        self.base_path = Path(base_path)
        self._cache: Dict[str, List[KnowledgeEntry]] = {}
        self._cache_signatures: Dict[str, tuple] = {}

        # Knowledge folders
        self.test_patterns_path = self.base_path / "test_patterns"
        self.locator_strategies_path = self.base_path / "locator_strategies"
        self.domain_knowledge_path = self.base_path / "domain_knowledge"
        self.best_practices_path = self.base_path / "best_practices"
        self.playwright_path = self.base_path / "playwright"

        # Ensure directories exist
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure knowledge base directories exist"""
        for path in [
            self.test_patterns_path,
            self.locator_strategies_path,
            self.domain_knowledge_path,
            self.best_practices_path,
            self.playwright_path,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def _load_file(self, file_path: Path) -> Optional[KnowledgeEntry]:
        """Load a knowledge file"""
        if not file_path.exists():
            return None

        try:
            if file_path.suffix == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return KnowledgeEntry(
                    title=data.get("title", file_path.stem),
                    content=data.get("content", ""),
                    category=data.get("category", ""),
                    tags=data.get("tags", []),
                    metadata=data.get("metadata", {}),
                )
            elif file_path.suffix in [".yaml", ".yml"]:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                return KnowledgeEntry(
                    title=data.get("title", file_path.stem),
                    content=data.get("content", ""),
                    category=data.get("category", ""),
                    tags=data.get("tags", []),
                    metadata=data.get("metadata", {}),
                )
            elif file_path.suffix == ".md":
                # Parse markdown file
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Extract frontmatter if present
                frontmatter_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
                metadata = {}
                if frontmatter_match:
                    try:
                        metadata = yaml.safe_load(frontmatter_match.group(1)) or {}
                        content = content[frontmatter_match.end() :]
                    except Exception:
                        logger.warning("Failed to parse YAML frontmatter in %s", file_path, exc_info=True)

                return KnowledgeEntry(
                    title=metadata.get("title", file_path.stem),
                    content=content,
                    category=metadata.get("category", ""),
                    tags=metadata.get("tags", []),
                    metadata=metadata,
                )
        except Exception:
            logger.warning("Failed to load knowledge file %s", file_path, exc_info=True)
            return None

        return None

    def _load_directory(self, directory: Path, category: str) -> List[KnowledgeEntry]:
        """Load all knowledge files from a directory"""
        entries = []

        if not directory.exists():
            return entries

        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.suffix in [".md", ".json", ".yaml", ".yml"]:
                entry = self._load_file(file_path)
                if entry:
                    entry.category = category
                    entries.append(entry)

        return entries

    @staticmethod
    def _directory_signature(directory: Path) -> tuple:
        if not directory.exists():
            return ()
        signature = []
        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file() and file_path.suffix in [".md", ".json", ".yaml", ".yml"]:
                stat = file_path.stat()
                signature.append((str(file_path.relative_to(directory)), stat.st_mtime_ns, stat.st_size))
        return tuple(signature)

    def _cached_or_load(self, cache_key: str, directory: Path, category: str) -> List[KnowledgeEntry]:
        signature = self._directory_signature(directory)
        if cache_key in self._cache and self._cache_signatures.get(cache_key) == signature:
            return self._cache[cache_key]
        entries = self._load_directory(directory, category)
        self._cache[cache_key] = entries
        self._cache_signatures[cache_key] = signature
        return entries

    def get_test_patterns(self, query: Optional[str] = None) -> List[KnowledgeEntry]:
        """
        Get test patterns.

        Args:
            query: Optional search query to filter patterns

        Returns:
            List of test pattern entries
        """
        cache_key = f"test_patterns:{query or 'all'}"
        entries = self._cached_or_load(cache_key, self.test_patterns_path, "test_patterns")

        if query:
            query_lower = query.lower()
            entries = [
                e
                for e in entries
                if query_lower in e.title.lower()
                or query_lower in e.content.lower()
                or any(query_lower in tag.lower() for tag in e.tags)
            ]

        return entries

    def get_locator_strategies(self, query: Optional[str] = None) -> List[KnowledgeEntry]:
        """
        Get locator strategies.

        Args:
            query: Optional search query to filter strategies

        Returns:
            List of locator strategy entries
        """
        cache_key = f"locator_strategies:{query or 'all'}"
        entries = self._cached_or_load(
            cache_key, self.locator_strategies_path, "locator_strategies"
        )

        if query:
            query_lower = query.lower()
            entries = [
                e
                for e in entries
                if query_lower in e.title.lower()
                or query_lower in e.content.lower()
                or any(query_lower in tag.lower() for tag in e.tags)
            ]

        return entries

    def get_domain_knowledge(self, domain: Optional[str] = None) -> List[KnowledgeEntry]:
        """
        Get domain knowledge.

        Args:
            domain: Optional domain name to filter knowledge

        Returns:
            List of domain knowledge entries
        """
        cache_key = f"domain_knowledge:{domain or 'all'}"
        entries = self._cached_or_load(cache_key, self.domain_knowledge_path, "domain_knowledge")

        if domain:
            domain_lower = domain.lower()
            entries = [
                e
                for e in entries
                if domain_lower in e.title.lower()
                or domain_lower in e.content.lower()
                or domain_lower in e.category.lower()
                or any(domain_lower in tag.lower() for tag in e.tags)
            ]

        return entries

    def get_best_practices(self, query: Optional[str] = None) -> List[KnowledgeEntry]:
        """
        Get best practices.

        Args:
            query: Optional search query to filter practices

        Returns:
            List of best practice entries
        """
        cache_key = f"best_practices:{query or 'all'}"
        entries = self._cached_or_load(cache_key, self.best_practices_path, "best_practices")

        if query:
            query_lower = query.lower()
            entries = [
                e
                for e in entries
                if query_lower in e.title.lower()
                or query_lower in e.content.lower()
                or any(query_lower in tag.lower() for tag in e.tags)
            ]

        return entries

    def get_playwright_knowledge(self, query: Optional[str] = None) -> List[KnowledgeEntry]:
        """
        Get Playwright best-practice rules (locators, assertions, waiting, security).

        Args:
            query: Optional search query to filter (e.g. 'locator', 'assertion', 'wait', 'security')

        Returns:
            List of Playwright knowledge entries
        """
        cache_key = f"playwright:{query or 'all'}"
        entries = self._cached_or_load(cache_key, self.playwright_path, "playwright")

        if query:
            query_lower = query.lower()
            entries = [
                e
                for e in entries
                if query_lower in e.title.lower()
                or query_lower in e.content.lower()
                or any(query_lower in tag.lower() for tag in e.tags)
            ]

        return entries

    def search(self, query: str, categories: Optional[List[str]] = None) -> List[KnowledgeEntry]:
        """
        Search across all knowledge bases.

        Args:
            query: Search query
            categories: Optional list of categories to search in

        Returns:
            List of matching knowledge entries
        """
        all_entries = []

        if categories is None:
            categories = [
                "test_patterns",
                "locator_strategies",
                "domain_knowledge",
                "best_practices",
                "playwright",
            ]

        if "test_patterns" in categories:
            all_entries.extend(self.get_test_patterns(query))
        if "locator_strategies" in categories:
            all_entries.extend(self.get_locator_strategies(query))
        if "domain_knowledge" in categories:
            all_entries.extend(self.get_domain_knowledge(query))
        if "best_practices" in categories:
            all_entries.extend(self.get_best_practices(query))
        if "playwright" in categories:
            all_entries.extend(self.get_playwright_knowledge(query))

        return all_entries

    def get_context_for_agent(self, agent_type: str, query: Optional[str] = None) -> str:
        """
        Get formatted context string for an agent.

        Args:
            agent_type: Type of agent ('test_generator', 'locator_expert', 'failure_analyzer')
            query: Optional query to filter knowledge

        Returns:
            Formatted context string
        """
        context_parts = []

        if agent_type == "test_generator":
            patterns = self.get_test_patterns(query)
            practices = self.get_best_practices(query)
            playwright_rules = self.get_playwright_knowledge()

            if patterns:
                context_parts.append("## Test Patterns")
                for pattern in patterns[:5]:  # Limit to top 5
                    context_parts.append(f"### {pattern.title}")
                    context_parts.append(pattern.content[:500])  # Limit content length

            if practices:
                context_parts.append("\n## Best Practices")
                for practice in practices[:3]:  # Limit to top 3
                    context_parts.append(f"### {practice.title}")
                    context_parts.append(practice.content[:500])

            if playwright_rules:
                context_parts.append("\n## Playwright Rules (Standard Script Creation)")
                for rule in playwright_rules[:10]:  # All 4 files + headroom
                    context_parts.append(f"### {rule.title}")
                    context_parts.append(rule.content[:800])  # Allow more for rules

        elif agent_type == "locator_expert":
            strategies = self.get_locator_strategies(query)
            playwright_rules = self.get_playwright_knowledge("locator")

            if strategies:
                context_parts.append("## Locator Strategies")
                for strategy in strategies[:5]:
                    context_parts.append(f"### {strategy.title}")
                    context_parts.append(strategy.content[:500])

            if playwright_rules:
                context_parts.append("\n## Playwright Locator Rules")
                for rule in playwright_rules[:5]:
                    context_parts.append(f"### {rule.title}")
                    context_parts.append(rule.content[:800])

        elif agent_type == "failure_analyzer":
            practices = self.get_best_practices("failure")
            patterns = self.get_test_patterns("error")

            if practices:
                context_parts.append("## Failure Analysis Practices")
                for practice in practices[:3]:
                    context_parts.append(f"### {practice.title}")
                    context_parts.append(practice.content[:500])

        return "\n\n".join(context_parts)
