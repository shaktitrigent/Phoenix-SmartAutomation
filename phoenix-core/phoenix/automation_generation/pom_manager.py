"""Universal POM Manager - Intelligent Page Object Generation and Reuse.

This module implements a generic POM manager that determines what belongs in
Page Objects, enables reuse of existing POMs, and generates new POMs when needed.

Priority 24: Universal Autonomous Test Automation Generation
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pydantic import BaseModel, Field

from phoenix.semantic.models import SemanticComponent, PageType

logger = logging.getLogger(__name__)


class POMSimilarityScore(BaseModel):
    """Similarity score between two POMs."""
    
    pom_id: str
    similarity: float
    shared_components: List[str]
    shared_actions: List[str]
    recommended_action: str  # reuse, extend, create_new


class POMMetadata(BaseModel):
    """Metadata for a Page Object."""
    
    pom_id: str
    pom_name: str
    page_type: PageType
    file_path: str
    
    # Components
    component_ids: List[str] = Field(default_factory=list)
    component_types: List[str] = Field(default_factory=list)
    
    # Methods
    method_names: List[str] = Field(default_factory=list)
    
    # Statistics
    total_methods: int = 0
    total_locators: int = 0
    
    # Reuse
    reuse_count: int = 0
    last_used: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Quality
    quality_score: float = Field(default=0.0, ge=0.0, le=100.0)
    
    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class POMManager:
    """Universal POM manager for intelligent Page Object generation and reuse.
    
    This manager:
    - Searches existing POMs for semantic similarity
    - Reuses compatible POMs
    - Extends POMs when necessary
    - Creates new POMs only when genuinely new
    - Supports maintainability and encapsulation
    - Centralizes locators
    - Provides readable methods
    """
    
    def __init__(
        self,
        pom_directory: str = "pages",
        base_pom_path: Optional[str] = None,
    ):
        self.pom_directory = Path(pom_directory)
        self.pom_directory.mkdir(parents=True, exist_ok=True)
        
        self.base_pom_path = base_pom_path or str(self.pom_directory / "base_page.py")
        
        # POM registry
        self.pom_registry: Dict[str, POMMetadata] = {}
        
        # Load existing POMs
        self._load_existing_poms()
        
        logger.info(
            f"POMManager initialized with {len(self.pom_registry)} existing POMs "
            f"in {self.pom_directory}"
        )
    
    def _load_existing_poms(self):
        """Load existing POMs from directory."""
        if not self.pom_directory.exists():
            return
        
        for pom_file in self.pom_directory.glob("*_page.py"):
            if pom_file.name == "base_page.py":
                continue
            
            try:
                metadata = self._extract_pom_metadata(pom_file)
                if metadata:
                    self.pom_registry[metadata.pom_id] = metadata
            except Exception as e:
                logger.warning(f"Failed to load POM metadata from {pom_file}: {e}")
    
    def _extract_pom_metadata(self, pom_file: Path) -> Optional[POMMetadata]:
        """Extract metadata from an existing POM file."""
        try:
            content = pom_file.read_text()
            
            # Extract class name
            class_match = re.search(r'class\s+(\w+Page)', content)
            if not class_match:
                return None
            
            class_name = class_match.group(1)
            pom_name = class_name.lower().replace("_page", "")
            
            # Extract page type from comments or class name
            page_type = self._infer_page_type(class_name, content)
            
            # Extract methods
            method_matches = re.findall(r'def\s+(\w+)\s*\(', content)
            method_names = [m for m in method_matches if not m.startswith("_")]
            
            # Extract locators (get_by_ patterns)
            locator_matches = re.findall(r'(get_by_\w+\([^)]+\))', content)
            
            metadata = POMMetadata(
                pom_id=f"POM-{uuid.uuid4().hex[:8].upper()}",
                pom_name=pom_name,
                page_type=page_type,
                file_path=str(pom_file),
                method_names=method_names,
                total_methods=len(method_names),
                total_locators=len(locator_matches),
            )
            
            return metadata
        
        except Exception as e:
            logger.warning(f"Error extracting POM metadata from {pom_file}: {e}")
            return None
    
    def _infer_page_type(self, class_name: str, content: str) -> PageType:
        """Infer page type from class name and content."""
        class_lower = class_name.lower()
        content_lower = content.lower()
        
        # Check for authentication
        if any(word in class_lower for word in ["login", "auth", "signin"]):
            return PageType.AUTHENTICATION_SCREEN
        
        # Check for dashboard
        if "dashboard" in class_lower or "home" in class_lower:
            return PageType.DASHBOARD
        
        # Check for search
        if "search" in class_lower:
            return PageType.SEARCH_SCREEN
        
        # Check for CRUD
        if any(word in class_lower for word in ["create", "edit", "update", "form"]):
            return PageType.CRUD_FORM
        
        # Check for table
        if "table" in class_lower or "list" in class_lower:
            return PageType.TABLE_VIEW
        
        # Check for report
        if "report" in class_lower:
            return PageType.REPORT_SCREEN
        
        # Check for settings
        if "setting" in class_lower or "config" in class_lower:
            return PageType.SETTINGS
        
        # Check for profile
        if "profile" in class_lower or "account" in class_lower:
            return PageType.PROFILE
        
        # Default
        return PageType.UNKNOWN
    
    def find_reusable_pom(
        self,
        page_type: PageType,
        components: List[SemanticComponent],
        required_actions: List[str],
        min_similarity: float = 0.7,
    ) -> Optional[POMMetadata]:
        """Find an existing POM that can be reused.
        
        Args:
            page_type: Type of page
            components: Components on the page
            required_actions: Actions required from the POM
            min_similarity: Minimum similarity threshold for reuse
            
        Returns:
            POMMetadata if reusable POM found, None otherwise
        """
        if not self.pom_registry:
            return None
        
        best_match = None
        best_similarity = 0.0
        
        for pom_id, metadata in self.pom_registry.items():
            # Check page type match
            if metadata.page_type != page_type and page_type != PageType.UNKNOWN:
                continue
            
            # Calculate similarity
            similarity = self._calculate_pom_similarity(
                metadata,
                components,
                required_actions,
            )
            
            if similarity > best_similarity and similarity >= min_similarity:
                best_similarity = similarity
                best_match = metadata
        
        if best_match:
            logger.info(
                f"Found reusable POM {best_match.pom_name} "
                f"with similarity {best_similarity:.2f}"
            )
            # Update reuse count
            best_match.reuse_count += 1
            best_match.last_used = datetime.now(timezone.utc).isoformat()
        
        return best_match
    
    def _calculate_pom_similarity(
        self,
        metadata: POMMetadata,
        components: List[SemanticComponent],
        required_actions: List[str],
    ) -> float:
        """Calculate similarity between required POM and existing POM."""
        if not components and not required_actions:
            return 0.5
        
        similarity_scores = []
        
        # Component type similarity
        if components:
            component_types = set(c.component_type.value for c in components)
            existing_types = set(metadata.component_types)
            
            if component_types and existing_types:
                intersection = component_types & existing_types
                union = component_types | existing_types
                component_similarity = len(intersection) / len(union) if union else 0.0
                similarity_scores.append(component_similarity)
        
        # Action similarity
        if required_actions and metadata.method_names:
            required_lower = [a.lower() for a in required_actions]
            existing_lower = [m.lower() for m in metadata.method_names]
            
            action_similarity = self._calculate_list_similarity(
                required_lower,
                existing_lower,
            )
            similarity_scores.append(action_similarity)
        
        # Page type match bonus
        if metadata.page_type != PageType.UNKNOWN:
            similarity_scores.append(0.2)
        
        # Average similarity
        if similarity_scores:
            return sum(similarity_scores) / len(similarity_scores)
        
        return 0.0
    
    def _calculate_list_similarity(self, list1: List[str], list2: List[str]) -> float:
        """Calculate similarity between two lists using SequenceMatcher."""
        if not list1 or not list2:
            return 0.0
        
        # Use SequenceMatcher on joined strings
        str1 = " ".join(sorted(list1))
        str2 = " ".join(sorted(list2))
        
        return SequenceMatcher(None, str1, str2).ratio()
    
    def generate_pom(
        self,
        page_type: PageType,
        components: List[SemanticComponent],
        required_actions: List[str],
        pom_name: Optional[str] = None,
    ) -> str:
        """Generate a new POM or reuse an existing one.
        
        Args:
            page_type: Type of page
            components: Components on the page
            required_actions: Required actions/methods
            pom_name: Optional POM name
            
        Returns:
            Path to generated or reused POM
        """
        # Try to find reusable POM
        reusable_pom = self.find_reusable_pom(page_type, components, required_actions)
        
        if reusable_pom:
            logger.info(f"Reusing existing POM: {reusable_pom.pom_name}")
            return reusable_pom.file_path
        
        # Generate new POM
        pom_name = pom_name or self._generate_pom_name(page_type)
        pom_path = self.pom_directory / f"{pom_name}_page.py"
        
        # Generate POM content
        pom_content = self._generate_pom_content(
            pom_name,
            page_type,
            components,
            required_actions,
        )
        
        # Write POM file
        pom_path.write_text(pom_content)
        
        # Register POM
        metadata = POMMetadata(
            pom_id=f"POM-{uuid.uuid4().hex[:8].upper()}",
            pom_name=pom_name,
            page_type=page_type,
            file_path=str(pom_path),
            component_ids=[c.component_id for c in components],
            component_types=[c.component_type.value for c in components],
            method_names=required_actions,
            total_methods=len(required_actions),
            total_locators=len(components),
        )
        self.pom_registry[metadata.pom_id] = metadata
        
        logger.info(f"Generated new POM: {pom_name}_page.py")
        return str(pom_path)
    
    def _generate_pom_name(self, page_type: PageType) -> str:
        """Generate a POM name from page type."""
        type_mapping = {
            PageType.AUTHENTICATION_SCREEN: "authentication",
            PageType.DASHBOARD: "dashboard",
            PageType.CRUD_FORM: "crud_form",
            PageType.SEARCH_SCREEN: "search",
            PageType.TABLE_VIEW: "table_view",
            PageType.REPORT_SCREEN: "report",
            PageType.SETTINGS: "settings",
            PageType.PROFILE: "profile",
        }
        return type_mapping.get(page_type, "generic")
    
    def _generate_pom_content(
        self,
        pom_name: str,
        page_type: PageType,
        components: List[SemanticComponent],
        required_actions: List[str],
    ) -> str:
        """Generate POM Python code."""
        class_name = f"{pom_name.replace('_', ' ').title().replace(' ', '')}Page"
        
        lines = [
            f'"""Page Object for {page_type.value.replace("_", " ").title()}."""',
            "",
            "from typing import Optional",
            "",
            "from phoenix.mappings.pages.base_page import BasePage",
            "",
            "",
            f"class {class_name}(BasePage):",
            f'    """Page Object for {page_type.value.replace("_", " ").title()}."""',
            "",
            "",
        ]
        
        # Add locators
        lines.append("    # Locators")
        for component in components:
            if component.selected_locator:
                locator_name = self._generate_locator_name(component)
                lines.append(f"    {locator_name} = \"{component.selected_locator}\"")
        
        lines.append("")
        
        # Add methods
        lines.append("    # Page Methods")
        for action in required_actions:
            method_name = self._generate_method_name(action)
            lines.append(f"    def {method_name}(self):")
            lines.append(f'        """{action.replace("_", " ").title()}."""')
            lines.append("        pass")
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_locator_name(self, component: SemanticComponent) -> str:
        """Generate a locator name from component."""
        if component.semantic_purpose:
            return f"{component.semantic_purpose}_locator"
        elif component.label:
            return f"{component.label.lower().replace(' ', '_')}_locator"
        elif component.text_content:
            return f"{component.text_content.lower().replace(' ', '_')[:20]}_locator"
        else:
            return f"{component.component_type.value}_locator"
    
    def _generate_method_name(self, action: str) -> str:
        """Generate a method name from action."""
        return action.lower().replace(" ", "_").replace("-", "_")
    
    def extend_pom(
        self,
        pom_path: str,
        new_components: List[SemanticComponent],
        new_actions: List[str],
    ) -> str:
        """Extend an existing POM with new components and actions.
        
        Args:
            pom_path: Path to existing POM
            new_components: New components to add
            new_actions: New actions to add
            
        Returns:
            Updated POM path
        """
        pom_file = Path(pom_path)
        if not pom_file.exists():
            logger.warning(f"POM file {pom_path} does not exist")
            return pom_path
        
        try:
            content = pom_file.read_text()
            
            # Add new locators
            if new_components:
                locator_section_start = content.find("# Locators")
                if locator_section_start != -1:
                    insert_position = content.find("\n\n", locator_section_start)
                    if insert_position != -1:
                        new_locators = []
                        for component in new_components:
                            if component.selected_locator:
                                locator_name = self._generate_locator_name(component)
                                new_locators.append(f"    {locator_name} = \"{component.selected_locator}\"")
                        
                        if new_locators:
                            content = (
                                content[:insert_position]
                                + "\n".join(new_locators)
                                + "\n"
                                + content[insert_position:]
                            )
            
            # Add new methods
            if new_actions:
                method_section_start = content.find("# Page Methods")
                if method_section_start != -1:
                    new_methods = []
                    for action in new_actions:
                        method_name = self._generate_method_name(action)
                        new_methods.append(f"    def {method_name}(self):")
                        new_methods.append(f'        """{action.replace("_", " ").title()}."""')
                        new_methods.append("        pass")
                        new_methods.append("")
                    
                    if new_methods:
                        content = content + "\n".join(new_methods)
            
            # Write updated content
            pom_file.write_text(content)
            
            # Update metadata
            for metadata in self.pom_registry.values():
                if metadata.file_path == pom_path:
                    metadata.component_ids.extend(c.component_id for c in new_components)
                    metadata.component_types.extend(c.component_type.value for c in new_components)
                    metadata.method_names.extend(new_actions)
                    metadata.total_methods += len(new_actions)
                    metadata.total_locators += len(new_components)
                    metadata.updated_at = datetime.now(timezone.utc).isoformat()
                    break
            
            logger.info(f"Extended POM {pom_path} with {len(new_components)} components and {len(new_actions)} actions")
            return pom_path
        
        except Exception as e:
            logger.error(f"Failed to extend POM {pom_path}: {e}")
            return pom_path
    
    def get_base_pom_import(self) -> str:
        """Get the base POM import statement."""
        return "from phoenix.mappings.pages.base_page import BasePage"
    
    def should_create_pom(
        self,
        components: List[SemanticComponent],
        actions: List[str],
    ) -> bool:
        """Determine if a new POM should be created.
        
        Returns:
            True if POM should be created, False if logic should be in test
        """
        # Create POM if multiple components
        if len(components) > 3:
            return True
        
        # Create POM if multiple actions
        if len(actions) > 2:
            return True
        
        # Create POM if reusable across scenarios
        # (This would need scenario context in a real implementation)
        
        return False
    
    def get_pom_reuse_statistics(self) -> Dict[str, Any]:
        """Get statistics about POM reuse."""
        total_poms = len(self.pom_registry)
        total_reuse = sum(m.reuse_count for m in self.pom_registry.values())
        
        reused_poms = sum(1 for m in self.pom_registry.values() if m.reuse_count > 0)
        
        return {
            "total_poms": total_poms,
            "total_reuse_count": total_reuse,
            "reused_poms": reused_poms,
            "reuse_rate": reused_poms / total_poms if total_poms > 0 else 0.0,
        }
