"""Configuration management for Phoenix SDK.

File discovery order (first match wins):
  1. Explicit path passed to `load(config_path=...)`
  2. `.phoenixrc`        — TOML format (recommended)
  3. `phoenix.yaml`      — YAML format (legacy)
  4. `config.yaml`       — YAML format (legacy)
  5. Environment variables only
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field


def _load_toml(path: Path) -> Dict[str, Any]:
    """Load a TOML file using stdlib tomllib (3.11+) or the tomli back-port."""
    if sys.version_info >= (3, 11):
        import tomllib

        with open(path, "rb") as fh:
            return tomllib.load(fh)
    else:
        import tomli  # type: ignore[import]

        with open(path, "rb") as fh:
            return tomli.load(fh)


class DatabaseConfig(BaseModel):
    """Database configuration"""

    url: str = Field(default="sqlite:///./phoenix.db", description="Database connection URL")
    pool_size: int = Field(default=5, description="Connection pool size")
    max_overflow: int = Field(default=10, description="Max overflow connections")


class IntelligenceConfig(BaseModel):
    """Phoenix intelligence API configuration"""

    base_url: str = Field(
        default="http://localhost:8001/api/v1", description="Intelligence API base URL"
    )
    timeout: int = Field(default=300, description="Request timeout in seconds (LLM generation can take up to 5 min)")
    retry_count: int = Field(default=3, description="Number of retries on failure")


class CacheConfig(BaseModel):
    """Cache configuration"""

    type: str = Field(default="memory", description="Cache type: memory or redis")
    ttl: int = Field(default=3600, description="Time to live in seconds")
    url: Optional[str] = Field(default=None, description="Redis URL if type is redis")


class LoggingConfig(BaseModel):
    """Logging configuration"""

    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format"
    )


class ProjectConfig(BaseModel):
    """Project settings"""

    default_project: str = Field(default="default", description="Default project name")
    # New schema fields (phoenix init ≥ v2)
    name: Optional[str] = Field(default=None, description="Project name (new schema)")
    base_url: Optional[str] = Field(default=None, description="Application base URL (new schema)")
    default_browser: str = Field(default="chromium", description="Default browser")
    # Legacy fields kept for backwards compatibility
    application_url: Optional[str] = Field(default=None, description="Default application URL")
    manual_output_dir: str = Field(
        default="./manual_tests", description="Manual test output directory"
    )
    test_output_dir: str = Field(default="./test_results", description="Test output directory")
    tests_dir: str = Field(default="./tests", description="Module-organised tests directory")
    test_data_dir: str = Field(default="./test_data", description="Generated test data directory")
    report_output_dir: str = Field(default="./reports", description="Report output directory")

    @property
    def resolved_name(self) -> str:
        return self.name or self.default_project

    @property
    def resolved_base_url(self) -> Optional[str]:
        return self.base_url or self.application_url


class PhoenixConfig(BaseModel):
    """Main Phoenix configuration"""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    intelligence: IntelligenceConfig = Field(default_factory=IntelligenceConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    project: ProjectConfig = Field(default_factory=ProjectConfig)

    @classmethod
    def from_env(cls) -> "PhoenixConfig":
        """Load configuration from environment variables"""
        return cls(
            database=DatabaseConfig(
                url=os.environ.get("PHOENIX_DATABASE_URL", "sqlite:///./phoenix.db"),
                pool_size=int(os.environ.get("PHOENIX_DATABASE_POOL_SIZE", "5")),
                max_overflow=int(os.environ.get("PHOENIX_DATABASE_MAX_OVERFLOW", "10")),
            ),
            intelligence=IntelligenceConfig(
                base_url=os.environ.get(
                    "PHOENIX_INTELLIGENCE_URL",
                    os.environ.get("PHOENIX_MCP_SERVER_URL", "http://localhost:8001/api/v1"),
                ),
                timeout=int(os.environ.get("PHOENIX_INTELLIGENCE_TIMEOUT", "300")),
                retry_count=int(os.environ.get("PHOENIX_INTELLIGENCE_RETRY_COUNT", "3")),
            ),
            cache=CacheConfig(
                type=os.environ.get("PHOENIX_CACHE_TYPE", "memory"),
                ttl=int(os.environ.get("PHOENIX_CACHE_TTL", "3600")),
                url=os.environ.get("PHOENIX_CACHE_URL"),
            ),
            logging=LoggingConfig(
                level=os.environ.get("PHOENIX_LOG_LEVEL", "INFO"),
                format=os.environ.get(
                    "PHOENIX_LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                ),
            ),
            project=ProjectConfig(
                default_project=os.environ.get("PHOENIX_DEFAULT_PROJECT", "default"),
                application_url=os.environ.get("PHOENIX_APPLICATION_URL"),
                base_url=os.environ.get("PHOENIX_BASE_URL"),
                manual_output_dir=os.environ.get("PHOENIX_MANUAL_OUTPUT_DIR", "./manual_tests"),
                test_output_dir=os.environ.get("PHOENIX_TEST_OUTPUT_DIR", "./test_results"),
                tests_dir=os.environ.get("PHOENIX_TESTS_DIR", "./tests"),
                test_data_dir=os.environ.get("PHOENIX_TEST_DATA_DIR", "./test_data"),
                report_output_dir=os.environ.get("PHOENIX_REPORT_OUTPUT_DIR", "./reports"),
            ),
        )

    @classmethod
    def from_file(cls, config_path: Optional[str] = None) -> "PhoenixConfig":
        """Load configuration from a TOML (.phoenixrc) or YAML file."""
        if config_path is None:
            current_dir = Path.cwd()
            for search_dir in [current_dir, current_dir.parent]:
                for filename in [".phoenixrc", "phoenix.yaml", "config.yaml"]:
                    candidate = search_dir / filename
                    if candidate.exists():
                        config_path = str(candidate)
                        break
                if config_path:
                    break

        if config_path is None or not Path(config_path).exists():
            return cls.from_env()

        cfg_path = Path(config_path)
        if cfg_path.suffix == "" or cfg_path.name == ".phoenixrc":
            # Treat as TOML
            config_data: Dict[str, Any] = _load_toml(cfg_path)
        else:
            with open(cfg_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}

        # Backward compatibility: map legacy "mcp" config to "intelligence"
        if "intelligence" not in config_data and "mcp" in config_data:
            config_data["intelligence"] = {
                "base_url": config_data["mcp"].get("server_url", "http://localhost:8001/api/v1"),
                "timeout": config_data["mcp"].get("timeout", 30),
                "retry_count": config_data["mcp"].get("retry_count", 3),
            }

        # Merge with environment variables (env takes precedence)
        config = cls(**config_data)

        # Resolve project output directories relative to the config file location.
        # This prevents generated files from being scattered when CLI is run from different CWDs.
        base_dir = Path(config_path).resolve().parent
        for attr in (
            "manual_output_dir",
            "test_output_dir",
            "tests_dir",
            "test_data_dir",
            "report_output_dir",
        ):
            raw = getattr(config.project, attr, None)
            if raw and not Path(raw).is_absolute():
                setattr(config.project, attr, str((base_dir / raw).resolve()))

        # Override with environment variables if present
        if os.environ.get("PHOENIX_DATABASE_URL"):
            config.database.url = os.environ["PHOENIX_DATABASE_URL"]
        if os.environ.get("PHOENIX_INTELLIGENCE_URL"):
            config.intelligence.base_url = os.environ["PHOENIX_INTELLIGENCE_URL"]
        elif os.environ.get("PHOENIX_MCP_SERVER_URL"):
            config.intelligence.base_url = os.environ["PHOENIX_MCP_SERVER_URL"]

        return config

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "PhoenixConfig":
        """Load configuration from file or environment (file takes precedence).

        If *config_path* is None, auto-discover `phoenix.yaml` or `config.yaml`
        in the current directory or its parent directory.
        """
        return cls.from_file(config_path)
