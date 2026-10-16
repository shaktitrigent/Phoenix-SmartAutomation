"""Portable project metadata for automation requests (no environment values)."""

from typing import Optional

from pydantic import BaseModel


class ProjectContext(BaseModel):
    """Client-resolved paths remain strings, including on a different server OS."""

    project_root: str
    application_url: Optional[str] = None
    page_name: str
    locator_directory: str
    environment_file: str
