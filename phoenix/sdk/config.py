"""Configuration management for Phoenix SDK"""

import os
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    """Database configuration"""
    url: str = Field(default="sqlite:///./phoenix.db", description="Database connection URL")
    pool_size: int = Field(default=5, description="Connection pool size")
    max_overflow: int = Field(default=10, description="Max overflow connections")


class MCPConfig(BaseModel):
    """MCP server configuration"""
    server_url: str = Field(default="http://localhost:8000", description="MCP server URL")
    timeout: int = Field(default=30, description="Request timeout in seconds")
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
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )


class ProjectConfig(BaseModel):
    """Project settings"""
    default_project: str = Field(default="default", description="Default project name")
    test_output_dir: str = Field(default="./test_results", description="Test output directory")
    report_output_dir: str = Field(default="./reports", description="Report output directory")


class PhoenixConfig(BaseModel):
    """Main Phoenix configuration"""
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
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
            mcp=MCPConfig(
                server_url=os.environ.get("PHOENIX_MCP_SERVER_URL", "http://localhost:8000"),
                timeout=int(os.environ.get("PHOENIX_MCP_TIMEOUT", "30")),
                retry_count=int(os.environ.get("PHOENIX_MCP_RETRY_COUNT", "3")),
            ),
            cache=CacheConfig(
                type=os.environ.get("PHOENIX_CACHE_TYPE", "memory"),
                ttl=int(os.environ.get("PHOENIX_CACHE_TTL", "3600")),
                url=os.environ.get("PHOENIX_CACHE_URL"),
            ),
            logging=LoggingConfig(
                level=os.environ.get("PHOENIX_LOG_LEVEL", "INFO"),
                format=os.environ.get(
                    "PHOENIX_LOG_FORMAT",
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                ),
            ),
            project=ProjectConfig(
                default_project=os.environ.get("PHOENIX_DEFAULT_PROJECT", "default"),
                test_output_dir=os.environ.get("PHOENIX_TEST_OUTPUT_DIR", "./test_results"),
                report_output_dir=os.environ.get("PHOENIX_REPORT_OUTPUT_DIR", "./reports"),
            ),
        )

    @classmethod
    def from_file(cls, config_path: Optional[str] = None) -> "PhoenixConfig":
        """Load configuration from YAML file"""
        if config_path is None:
            # Look for config.yaml in current directory or parent directories
            current_dir = Path.cwd()
            for path in [current_dir, current_dir.parent]:
                config_file = path / "config.yaml"
                if config_file.exists():
                    config_path = str(config_file)
                    break

        if config_path is None or not Path(config_path).exists():
            # Fall back to environment variables
            return cls.from_env()

        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f) or {}

        # Merge with environment variables (env takes precedence)
        config = cls(**config_data)
        
        # Override with environment variables if present
        if os.environ.get("PHOENIX_DATABASE_URL"):
            config.database.url = os.environ["PHOENIX_DATABASE_URL"]
        if os.environ.get("PHOENIX_MCP_SERVER_URL"):
            config.mcp.server_url = os.environ["PHOENIX_MCP_SERVER_URL"]

        return config

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "PhoenixConfig":
        """Load configuration from file or environment (file takes precedence)"""
        if config_path and Path(config_path).exists():
            return cls.from_file(config_path)
        return cls.from_env()
