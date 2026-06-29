"""Abstract target adapter interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class CliResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float


class TargetAdapter(ABC):
    @abstractmethod
    def setup(self) -> None: ...

    @abstractmethod
    def start_server(self) -> None: ...

    @abstractmethod
    def stop_server(self) -> None: ...

    @abstractmethod
    def health_url(self) -> str: ...

    @abstractmethod
    def api_base_url(self) -> str: ...

    @abstractmethod
    def run_cli(self, args: List[str], cwd: str) -> CliResult: ...

    @abstractmethod
    def teardown(self) -> None: ...
