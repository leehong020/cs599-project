"""LLM 客户端。

封装 DeepSeek API 调用。DeepSeek 兼容 OpenAI chat API，
因此直接使用 langchain-openai 的 ChatOpenAI。

同步版本用于 LangGraph 节点（graph.invoke 是同步的），
异步版本用于 FastAPI 端点。
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import REPO_ROOT, get_settings


def _build_chat_model() -> ChatOpenAI:
    """根据配置创建 ChatOpenAI 实例。"""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        temperature=0.3,
        max_tokens=2048,
        # 外部模型偶发慢响应时，必须让图有机会返回友好兜底文案。
        timeout=settings.llm_timeout_seconds,
        max_retries=1,
    )


_chat_model: ChatOpenAI | None = None


def get_chat_model() -> ChatOpenAI:
    """返回缓存的 LLM 实例。"""
    global _chat_model
    if _chat_model is None:
        _chat_model = _build_chat_model()
    return _chat_model


def load_prompt(name: str) -> str:
    """从 config/prompts/ 目录加载 .md 提示词模板。"""
    prompt_dir = REPO_ROOT / "src" / "backend" / "app" / "config" / "prompts"
    path = prompt_dir / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"提示词模板不存在：{path}")
    return path.read_text(encoding="utf-8")


def build_system_prompt(context: dict[str, Any] | None = None) -> str:
    """构建完整系统提示词，注入上下文 JSON 和日期/时区。"""
    from datetime import datetime, timezone as dt_timezone, timedelta
    beijing_tz = dt_timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz)
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

    base = load_prompt("system_prompt")
    ctx_str = json.dumps(context or {}, ensure_ascii=False, indent=2)
    return (
        base.replace("{context}", ctx_str)
            .replace("{today}", now.strftime(f"%Y年%m月%d日 {weekday_names[now.weekday()]}"))
            .replace("{current_time}", now.strftime("%H:%M"))
    )


def llm_invoke(messages: list) -> str:
    """同步调用 LLM，返回文本。用于 LangGraph 同步节点。"""
    model = get_chat_model()
    response = model.invoke(messages)
    content = response.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(c) for c in content)
    return str(content)


def llm_invoke_structured(messages: list, schema: type[BaseModel]) -> dict[str, Any] | None:
    """同步调用 LLM，返回结构化输出。用于 LangGraph 同步节点。"""
    model = get_chat_model()
    structured = model.with_structured_output(schema)
    try:
        result = structured.invoke(messages)
        if result is None:
            return None
        if isinstance(result, dict):
            return result
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return None
    except Exception:
        return None


async def generate_response(system_prompt: str, user_message: str) -> str:
    """异步调用 LLM 生成自然语言回复。用于 FastAPI 端点。"""
    model = get_chat_model()
    response = await model.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ])
    content = response.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(c) for c in content)
    return str(content)


async def generate_structured_output(
    system_prompt: str,
    user_message: str,
    schema: type[BaseModel],
) -> dict[str, Any] | None:
    """异步调用 LLM 生成结构化输出。用于 FastAPI 端点。"""
    model = get_chat_model()
    structured = model.with_structured_output(schema)
    try:
        result = await structured.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])
        if result is None:
            return None
        if isinstance(result, dict):
            return result
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return None
    except Exception:
        return None


def stream_response(system_prompt: str, user_message: str):
    """同步流式调用 LLM，逐 token yield。用于 SSE 实时输出。"""
    model = get_chat_model()
    for chunk in model.stream([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]):
        content = chunk.content
        if isinstance(content, str) and content:
            yield content
        elif isinstance(content, list):
            for c in content:
                if c:
                    yield str(c)


def reset_chat_model_for_tests() -> None:
    """清理 LLM 实例缓存，供测试时使用。"""
    global _chat_model
    _chat_model = None
