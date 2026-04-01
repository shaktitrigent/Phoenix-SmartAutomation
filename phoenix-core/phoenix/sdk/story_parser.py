"""User story file parser for phoenix-core."""

from dataclasses import dataclass
from typing import List


@dataclass
class ParsedStory:
    """Parsed user story with acceptance criteria."""

    title: str
    acceptance_criteria: List[str]


def parse_user_story_file(text: str) -> List[ParsedStory]:
    """
    Parse a user story text file into structured stories.

    Expected format (repeated):
      User Story X — <Header>
      Title:
      <Story text>
      Acceptance Criteria:
      <criteria line 1>
      <criteria line 2>
    """
    cleaned_text = text.replace("\ufeff", "")
    lines = [line.strip() for line in cleaned_text.splitlines()]
    stories: List[ParsedStory] = []
    current_title = ""
    current_criteria: List[str] = []
    in_title = False
    in_criteria = False

    def flush_story():
        nonlocal current_title, current_criteria
        if current_title:
            stories.append(
                ParsedStory(
                    title=current_title.strip(),
                    acceptance_criteria=[c for c in current_criteria if c],
                )
            )
        current_title = ""
        current_criteria = []

    for line in lines:
        if not line:
            continue

        normalized = " ".join(line.split()).lower()

        if "user story" in normalized:
            flush_story()
            in_title = True
            in_criteria = False
            # Capture title: "User Story X — <Header>" or "User Story: <Story text>"
            parts = line.split("—", 1)
            if len(parts) == 2 and parts[1].strip():
                current_title = parts[1].strip()
            elif ":" in line:
                after_colon = line.split(":", 1)[1].strip()
                if after_colon:
                    current_title = after_colon
            continue

        if normalized.startswith("title:"):
            in_title = True
            in_criteria = False
            title_value = line.split(":", 1)[1].strip()
            if title_value:
                current_title = f"{current_title} {title_value}".strip()
            continue

        if normalized.startswith("acceptance criteria"):
            in_criteria = True
            in_title = False
            continue

        if normalized.startswith("application url"):
            in_title = False
            in_criteria = False
            continue

        if in_title:
            if line.strip("-").strip() == "":
                continue
            current_title = f"{current_title} {line}".strip()
            continue

        if in_criteria:
            current_criteria.append(line.lstrip("- ").strip())

    flush_story()
    return stories
