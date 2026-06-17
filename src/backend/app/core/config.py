from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

def _find_repo_root() -> Path:
    """从当前文件向上查找课程仓库根目录。

    项目提交结构把后端放在 `src/backend` 下，不能再依赖固定的
    `parents[n]` 层级。用 README、.env.example 和 src 目录共同定位仓库根，
    可以避免 Alembic、pytest、uvicorn 从不同目录启动时读到不同的数据目录。
    """
    for parent in Path(__file__).resolve().parents:
        if (
            (parent / "README.md").exists()
            and (parent / ".env.example").exists()
            and (parent / "src").is_dir()
        ):
            return parent
    return Path(__file__).resolve().parents[4]


# 所有运行时路径都从仓库根目录解析，而不是从当前命令所在目录解析。
# Alembic、pytest、uvicorn 可能从不同目录启动，但它们必须共用同一份
# SQLite 文件，否则会出现"迁移成功但应用读的是另一份库"的隐蔽问题。
REPO_ROOT = _find_repo_root()
DEFAULT_DATABASE_URL = (
    f"sqlite+aiosqlite:///{(REPO_ROOT / 'data' / 'runtime' / 'app.sqlite3').as_posix()}"
)
DEFAULT_LANGGRAPH_DB_PATH = (REPO_ROOT / "data" / "runtime" / "langgraph.sqlite3").as_posix()


def _try_load_google_oauth_json() -> dict[str, str]:
    """尝试从仓库根目录的 google_oauth.json 读取 OAuth 凭据。

    Google Cloud Console 下载的 OAuth 客户端 JSON 文件格式：
    {"web": {"client_id": "...", "client_secret": "...", "redirect_uris": [...]}}

    如果文件不存在或格式不对，返回空 dict。
    """
    json_path = REPO_ROOT / "google_oauth.json"
    if not json_path.exists():
        return {}

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        web = data.get("web", data)
        return {
            "client_id": web.get("client_id", ""),
            "client_secret": web.get("client_secret", ""),
            "redirect_uri": (
                web.get("redirect_uris", [None])[0]
                if web.get("redirect_uris")
                else "http://localhost:8000/gmail/auth/callback"
            ),
        }
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


class Settings(BaseSettings):
    """从环境变量和 `.env` 读取运行时配置。

    支持两种 Google OAuth 配置方式（优先级从高到低）：
    1. `.env` 中的 GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
    2. 仓库根目录的 google_oauth.json（Google Cloud Console 下载的文件）

    默认值只用于本地开发。真实密钥必须放在未提交的 `.env` 或 JSON 文件中。
    """

    # 后端和前端地址分开配置。
    app_env: str = "development"
    app_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5173"

    # SQLite 是 MVP 的事实来源。
    database_url: str = DEFAULT_DATABASE_URL
    langgraph_db_path: str = DEFAULT_LANGGRAPH_DB_PATH

    # Token 加密 key。生产环境必须更换。
    token_encryption_key: str = "replace-me"

    # Google OAuth 配置。如果 env 中是 replace-me，会自动尝试从
    # google_oauth.json 读取——这是 Google Cloud Console 下载的文件格式。
    google_client_id: str = "replace-me"
    google_client_secret: str = "replace-me"
    google_redirect_uri: str = "http://localhost:8000/gmail/auth/callback"
    google_oauth_scopes: str = (
        "openid email profile "
        "https://www.googleapis.com/auth/gmail.modify "
        "https://www.googleapis.com/auth/calendar.events "
        "https://www.googleapis.com/auth/calendar.freebusy"
    )
    _google_oauth_json_loaded: bool = False

    # DeepSeek LLM 配置。
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-v4-flash"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = Field(default="replace-me", repr=False)
    # 单次模型请求的超时时间，避免外部模型服务无响应时聊天页一直等待。
    llm_timeout_seconds: float = 45.0

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "src" / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _load_google_oauth_from_json(self) -> Settings:
        """如果 env 中 Google OAuth 是占位值，尝试从 JSON 文件读取。"""
        if self._google_oauth_json_loaded:
            return self

        client_id_is_placeholder = (
            not self.google_client_id or self.google_client_id == "replace-me"
        )
        client_secret_is_placeholder = (
            not self.google_client_secret or self.google_client_secret == "replace-me"
        )

        if client_id_is_placeholder or client_secret_is_placeholder:
            json_creds = _try_load_google_oauth_json()
            if json_creds.get("client_id") and json_creds.get("client_secret"):
                object.__setattr__(self, "google_client_id", json_creds["client_id"])
                object.__setattr__(self, "google_client_secret", json_creds["client_secret"])
                if json_creds.get("redirect_uri"):
                    object.__setattr__(self, "google_redirect_uri", json_creds["redirect_uri"])

        object.__setattr__(self, "_google_oauth_json_loaded", True)
        return self

    @property
    def runtime_dir(self) -> Path:
        """保存 SQLite 数据库和本地运行日志的目录。"""
        return REPO_ROOT / "data" / "runtime"

    @property
    def exports_dir(self) -> Path:
        """保存 Markdown 导出文件的目录。"""
        return REPO_ROOT / "data" / "exports"

    @property
    def uploads_dir(self) -> Path:
        """保存用户上传原始文件的目录。

        上传文件属于本地运行数据，不能提交到仓库。解析后的文本也只作为
        不可信上下文参与草稿生成，不能直接授权外部写操作。
        """
        return REPO_ROOT / "data" / "uploads"


@lru_cache
def get_settings() -> Settings:
    """返回缓存后的配置对象。"""
    return Settings()
