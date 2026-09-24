"""Persistent Locator Repository - Reusable locator storage with learning.

This module implements a persistent locator repository that:
- Stores locators outside of logs for reuse
- Organizes locators by project/application
- Tracks locator confidence and usage statistics
- Updates confidence based on execution results
- Avoids unnecessary LLM calls for known elements
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Locator Models
# ---------------------------------------------------------------------------

class LocatorEntry(BaseModel):
    """Single locator entry with learning metadata."""
    locator: str = Field(..., description="Playwright locator string")
    locator_type: str = Field(..., description="Type: get_by_role, get_by_text, etc.")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score")
    validated: bool = False
    success_count: int = 0
    failure_count: int = 0
    last_used: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_validation: str = ""
    source: str = ""  # mcp, manual, healing
    element_name: str = ""
    page_url: str = ""
    priority: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProjectLocators(BaseModel):
    """Locators for a specific project/page."""
    project_name: str = ""
    page_name: str = ""
    elements: Dict[str, LocatorEntry] = Field(default_factory=dict)
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1


# ---------------------------------------------------------------------------
# Persistent Locator Repository
# ---------------------------------------------------------------------------

class LocatorRepository:
    """Persistent locator repository with learning capabilities.
    
    Features:
    - Project-based organization
    - Confidence tracking with learning
    - Usage statistics
    - Validation tracking
    - Automatic updates from healing
    """
    
    def __init__(
        self,
        repository_dir: str | Path = "locators",
        artifacts_manager=None,
    ):
        self.repository_dir = Path(repository_dir)
        self.repository_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_manager = artifacts_manager
        
        # In-memory cache
        self.projects: Dict[str, ProjectLocators] = {}
        
        # Load existing repository
        self._load_repository()
    
    def get_locator(
        self,
        project_name: str,
        page_name: str,
        element_name: str,
        min_confidence: float = 0.7
    ) -> Optional[LocatorEntry]:
        """Get locator for element from repository.
        
        Args:
            project_name: Project/application name
            page_name: Page name
            element_name: Element name
            min_confidence: Minimum confidence threshold
            
        Returns:
            Locator entry if found and meets confidence threshold
        """
        project_key = self._project_key(project_name, page_name)
        project = self.projects.get(project_key)
        
        if not project:
            return None
        
        locator = project.elements.get(element_name)
        
        if not locator:
            return None
        
        # Check confidence threshold
        if locator.confidence < min_confidence:
            return None
        
        # Check if validated recently (within 24 hours)
        if locator.last_validation:
            try:
                last_val = datetime.fromisoformat(locator.last_validation)
                age = (datetime.now(timezone.utc) - last_val).total_seconds()
                if age > 86400:  # 24 hours
                    # Stale validation - require revalidation
                    return None
            except:
                pass
        
        return locator
    
    def save_locator(
        self,
        project_name: str,
        page_name: str,
        element_name: str,
        locator: str,
        locator_type: str = "unknown",
        confidence: float = 0.5,
        source: str = "manual",
        page_url: str = "",
        priority: int = 0,
        metadata: Dict[str, Any] = None
    ) -> LocatorEntry:
        """Save or update locator in repository.
        
        Args:
            project_name: Project/application name
            page_name: Page name
            element_name: Element name
            locator: Playwright locator string
            locator_type: Type of locator
            confidence: Initial confidence score
            source: Source of locator
            page_url: Page URL
            priority: Locator priority
            metadata: Additional metadata
            
        Returns:
        """
        logger.info(f"[LOCATOR REPOSITORY] SAVE LOCATOR - Project: {project_name}, Page: {page_name}, Element: {element_name}")
        logger.info(f"[LOCATOR REPOSITORY] SAVE LOCATOR - Locator: {locator}, Confidence: {confidence}")
        
        project_key = self._project_key(project_name, page_name)
        
        # Get or create project
        project = self.projects.get(project_key)
        if not project:
            project = ProjectLocators(
                project_name=project_name,
                page_name=page_name
            )
            self.projects[project_key] = project
        
        # Create or update locator entry
        existing = project.elements.get(element_name)
        
        if existing:
            # Update existing entry
            existing.locator = locator
            existing.locator_type = locator_type
            existing.source = source
            existing.page_url = page_url
            existing.priority = priority
            if metadata:
                existing.metadata.update(metadata)
            existing.last_used = datetime.now(timezone.utc).isoformat()
            entry = existing
        else:
            # Create new entry
            entry = LocatorEntry(
                locator=locator,
                locator_type=locator_type,
                confidence=confidence,
                source=source,
                element_name=element_name,
                page_url=page_url,
                priority=priority,
                metadata=metadata or {}
            )
            project.elements[element_name] = entry
        
        project.last_updated = datetime.now(timezone.utc).isoformat()
        project.version += 1
        
        # Persist to disk
        self._save_project(project_name, page_name, project)
        
        return entry
    
    def record_success(
        self,
        project_name: str,
        page_name: str,
        element_name: str
    ) -> None:
        """Record successful locator usage.
        
        Args:
            project_name: Project name
            page_name: Page name
            element_name: Element name
        """
        project_key = self._project_key(project_name, page_name)
        project = self.projects.get(project_key)
        
        if not project:
            return
        
        locator = project.elements.get(element_name)
        if not locator:
            return
        
        # Update statistics
        locator.success_count += 1
        locator.last_used = datetime.now(timezone.utc).isoformat()
        
        # Increase confidence based on success
        self._update_confidence(locator, success=True)
        
        # Persist
        self._save_project(project_name, page_name, project)
    
    def record_failure(
        self,
        project_name: str,
        page_name: str,
        element_name: str
    ) -> None:
        """Record locator failure.
        
        Args:
            project_name: Project name
            page_name: Page name
            element_name: Element name
        """
        project_key = self._project_key(project_name, page_name)
        project = self.projects.get(project_key)
        
        if not project:
            return
        
        locator = project.elements.get(element_name)
        if not locator:
            return
        
        # Update statistics
        locator.failure_count += 1
        locator.last_used = datetime.now(timezone.utc).isoformat()
        
        # Decrease confidence based on failure
        self._update_confidence(locator, success=False)
        
        # Persist
        self._save_project(project_name, page_name, project)
    
    def record_validation(
        self,
        project_name: str,
        page_name: str,
        element_name: str,
        validated: bool
    ) -> None:
        """Record locator validation result.
        
        Args:
            project_name: Project name
            page_name: Page name
            element_name: Element name
            validated: Whether validation passed
        """
        project_key = self._project_key(project_name, page_name)
        project = self.projects.get(project_key)
        
        if not project:
            return
        
        locator = project.elements.get(element_name)
        if not locator:
            return
        
        locator.validated = validated
        locator.last_validation = datetime.now(timezone.utc).isoformat()
        
        # Persist
        self._save_project(project_name, page_name, project)
    
    def get_improved_locator(
        self,
        selector: str,
        url: str,
        project: str,
        min_confidence: float = 0.7
    ) -> Optional[str]:
        """Get improved locator from repository for a given selector.
        
        Args:
            selector: Current selector string
            url: Current page URL
            project: Project name
            min_confidence: Minimum confidence threshold
            
        Returns:
            Improved locator if available, None otherwise
        """
        logger.info(f"[LOCATOR REPOSITORY] GET IMPROVED LOCATOR - Selector: {selector}, URL: {url}, Project: {project}")
        # Extract page name from URL or use project name
        page_name = self._extract_page_name(url, project)
        
        # Look for locators that might match the current selector's element
        project_key = self._project_key(project, page_name)
        project_data = self.projects.get(project_key)
        
        if not project_data:
            logger.info(f"[LOCATOR REPOSITORY] No project data found for {project_key}")
            return None
        
        # Check if there's a locator with higher confidence for similar element
        for element_name, locator_entry in project_data.elements.items():
            logger.info(f"[LOCATOR REPOSITORY] Checking {element_name}: selector={locator_entry.locator}, confidence={locator_entry.confidence}, validated={locator_entry.validated}")
            if locator_entry.confidence >= min_confidence and locator_entry.validated:
                # Return if exact match (self-validation) or if selector is basic and we have a better one
                if locator_entry.locator == selector or (self._is_basic_selector(selector) and locator_entry.page_url == url):
                    logger.info(f"[LOCATOR REPOSITORY] Returning improved locator: {locator_entry.locator}")
                    return locator_entry.locator
                else:
                    logger.info(f"[LOCATOR REPOSITORY] Exact match found but URL check failed: locator_url={locator_entry.page_url}, current_url={url}")
        
        logger.info(f"[LOCATOR REPOSITORY] No improved locator found for {selector}")
        return None
    
    def _extract_page_name(self, url: str, project: str) -> str:
        """Extract page name from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            if path:
                # Use last path component as page name
                return path.split('/')[-1] or project
            return project
        except:
            return project
    
    def _is_basic_selector(self, selector: str) -> bool:
        """Check if selector is basic (could be improved)."""
        basic_patterns = ['#', '.', '[data-test', '[name=', '[id=']
        return any(pattern in selector for pattern in basic_patterns) or len(selector) < 20
        
        # Persist
        self._save_project(project_name, page_name, project)
    
    def get_all_locators(
        self,
        project_name: str,
        page_name: str
    ) -> Dict[str, LocatorEntry]:
        """Get all locators for a project/page.
        
        Args:
            project_name: Project name
            page_name: Page name
            
        Returns:
            Dictionary of element_name -> LocatorEntry
        """
        project_key = self._project_key(project_name, page_name)
        project = self.projects.get(project_key)
        
        if not project:
            return {}
        
        return project.elements.copy()
    
    def _update_confidence(self, locator: LocatorEntry, success: bool) -> None:
        """Update confidence based on success/failure.
        
        Uses a simple learning algorithm:
        - Success: confidence = min(1.0, confidence + 0.05)
        - Failure: confidence = max(0.0, confidence - 0.1)
        """
        if success:
            locator.confidence = min(1.0, locator.confidence + 0.05)
        else:
            locator.confidence = max(0.0, locator.confidence - 0.1)
    
    def _project_key(self, project_name: str, page_name: str) -> str:
        """Generate project key."""
        return f"{project_name}/{page_name}"
    
    def _save_project(
        self,
        project_name: str,
        page_name: str,
        project: ProjectLocators
    ) -> None:
        """Save project locators to disk."""
        project_dir = self.repository_dir / project_name
        project_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = project_dir / f"{page_name}.json"
        file_path.write_text(project.model_dump_json(indent=2), encoding='utf-8')
    
    def _load_repository(self) -> None:
        """Load all projects from disk."""
        if not self.repository_dir.exists():
            return
        
        for project_dir in self.repository_dir.iterdir():
            if not project_dir.is_dir():
                continue
            
            project_name = project_dir.name
            
            for locator_file in project_dir.glob("*.json"):
                page_name = locator_file.stem
                
                try:
                    data = json.loads(locator_file.read_text(encoding='utf-8'))
                    project = ProjectLocators(**data)
                    
                    # Convert elements dict to LocatorEntry objects
                    elements = {}
                    for elem_name, elem_data in data.get("elements", {}).items():
                        elements[elem_name] = LocatorEntry(**elem_data)
                    project.elements = elements
                    
                    project_key = self._project_key(project_name, page_name)
                    self.projects[project_key] = project
                    
                except Exception as e:
                    # Skip corrupted files
                    continue
    
    def clear(self) -> None:
        """Clear all locators from repository."""
        self.projects.clear()
        
        # Remove all repository files
        if self.repository_dir.exists():
            for project_dir in self.repository_dir.iterdir():
                if project_dir.is_dir():
                    shutil.rmtree(project_dir)