# ============================================================
# SECTION: mcp-server-config
# PURPOSE: MCP server configuration — env-based, no hardcoded secrets
# DOC: docs/sections/mcp-server-architecture.md
# ============================================================

"""
MCP server configuration.
Loads all settings from environment variables (via .env file).
No hardcoded credentials, IPs, or tokens.
"""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_file)


class McpDatabaseSettings(BaseSettings):
    """PostgreSQL connection settings for MCP server."""

    host: str = Field(default="localhost", alias="DB_HOST")
    port: int = Field(default=5432, alias="DB_PORT")
    database: str = Field(default="deklarant_pro", alias="DB_NAME")
    user: str = Field(default="postgres", alias="DB_USER")
    password: str = Field(..., alias="DB_PASSWORD")

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def connection_string(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


class McpServerSettings(BaseSettings):
    """MCP server operational settings."""

    name: str = Field(default="deklarant-pro-mcp", alias="MCP_SERVER_NAME")
    port: int = Field(default=8765, alias="MCP_SERVER_PORT")
    max_connections: int = Field(default=5, alias="MCP_MAX_CONNECTIONS")
    fuzzy_threshold: float = Field(
        default=0.92, alias="MCP_FUZZY_THRESHOLD"
    )
    max_declaration_items: int = Field(
        default=99, alias="MCP_MAX_DECLARATION_ITEMS"
    )

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )


# Singletons
_db_settings: McpDatabaseSettings | None = None
_server_settings: McpServerSettings | None = None


def get_db_settings() -> McpDatabaseSettings:
    global _db_settings
    if _db_settings is None:
        _db_settings = McpDatabaseSettings()
    return _db_settings


def get_server_settings() -> McpServerSettings:
    global _server_settings
    if _server_settings is None:
        _server_settings = McpServerSettings()
    return _server_settings
