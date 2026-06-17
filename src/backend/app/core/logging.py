from __future__ import annotations

import json
import logging
import re
from typing import Any


# 阶段 10 的日志脱敏规则集中放在这里，避免各业务服务各写一套不一致的
# replace 逻辑。后续如果接入更多供应商 token，只需要补充这个列表。
SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(access[_-]?token\s*[=:]\s*)[^,\s\]}]+", re.IGNORECASE),
    re.compile(r"(refresh[_-]?token\s*[=:]\s*)[^,\s\]}]+", re.IGNORECASE),
    re.compile(r"(client[_-]?secret\s*[=:]\s*)[^,\s\]}]+", re.IGNORECASE),
    re.compile(r"(api[_-]?key\s*[=:]\s*)[^,\s\]}]+", re.IGNORECASE),
    re.compile(r"(authorization\s*:\s*bearer\s+)[^,\s\]}]+", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)

SENSITIVE_TEXT_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "api_key",
    "authorization",
    "prompt",
    "body",
    "email_body",
    "content",
    "message_body",
}

AUDIT_EVENT_NAMES = {
    "work_item.created",
    "work_item.revised",
    "work_item.deferred",
    "proposal.created",
    "proposal.revised",
    "proposal.approved",
    "proposal.rejected",
    "action.executing",
    "action.succeeded",
    "action.failed",
    "memory.candidate_created",
    "memory.activated",
}

AUDIT_ALLOWED_FIELDS = {
    "thread_id",
    "work_item_id",
    "proposal_item_id",
    "action_type",
    "status",
    "from_status",
    "to_status",
    "duration_ms",
    "error_category",
    "event_id",
    "memory_id",
}

REDACTION = "[REDACTED]"


def redact_text(value: object) -> str:
    """把任意日志值转换成脱敏后的字符串。

    这个函数同时处理普通字符串和 dict/list 等结构化对象。结构化对象会先按
    key 粗粒度隐藏完整 Prompt、邮件正文等大段敏感文本，再做正则级 token
    脱敏，保证即使调用方误把 token 拼进字符串，也不会直接进入日志。
    """
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(_redact_structured_value(value), ensure_ascii=False, default=str)
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub(
            lambda match: f"{match.group(1)}{REDACTION}" if match.groups() else REDACTION,
            text,
        )
    return text


def _redact_structured_value(value: object) -> object:
    """递归脱敏结构化日志对象中的敏感字段。"""
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key in SENSITIVE_TEXT_KEYS:
                redacted[str(key)] = REDACTION
            else:
                redacted[str(key)] = _redact_structured_value(item)
        return redacted
    if isinstance(value, list | tuple | set):
        return [_redact_structured_value(item) for item in value]
    return value


class RedactingFilter(logging.Filter):
    """日志过滤器，在所有 handler 输出前统一做脱敏。

    Python logging 会先把 msg 和 args 合并成最终文本。这里主动调用
    `record.getMessage()` 得到合并后的内容，再清空 args，避免 handler 格式化
    时重复插值或绕过脱敏结果。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return True


def configure_logging() -> None:
    """配置本地开发日志格式和脱敏过滤器。

    阶段 10 要求 token、client secret、完整 Prompt 和完整邮件正文不得进入
    日志。这里把 RedactingFilter 挂到 root logger 以及已有 handler 上，让
    FastAPI、业务服务和测试中新增的 logger 都能继承同一条规则。
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s [%(name)s] %(message)s",
    )
    _configure_log_record_factory()
    root_logger = logging.getLogger()
    _ensure_redacting_filter(root_logger)
    for handler in root_logger.handlers:
        _ensure_redacting_filter(handler)


def audit_log_event(event_type: str, **fields: Any) -> None:
    """写入一条脱敏审计日志。

    审计日志只允许记录可追踪但不敏感的字段，例如 thread_id、work_item_id、
    proposal_item_id、动作类型、状态变化、耗时和错误分类。任何未在白名单中
    的字段都会被丢弃，避免调用方无意中把正文或 token 传进审计流。
    """
    if event_type not in AUDIT_EVENT_NAMES:
        raise ValueError(f"未知审计事件：{event_type}")
    payload = {
        "event_type": event_type,
        **{key: value for key, value in fields.items() if key in AUDIT_ALLOWED_FIELDS},
    }
    logging.getLogger("mailflow.audit").info(redact_text(payload))


def log_error_trace(error_category: str, **fields: Any) -> None:
    """记录可追踪错误信息，但不记录敏感业务正文。"""
    payload = {
        "error_category": error_category,
        **{key: value for key, value in fields.items() if key in AUDIT_ALLOWED_FIELDS},
    }
    logging.getLogger("mailflow.error").warning(redact_text(payload))


def _ensure_redacting_filter(target: logging.Filterer) -> None:
    """确保同一个 logger 或 handler 上只挂一个脱敏过滤器。"""
    if not any(isinstance(item, RedactingFilter) for item in target.filters):
        target.addFilter(RedactingFilter())


def _configure_log_record_factory() -> None:
    """在 LogRecord 创建阶段脱敏，覆盖测试和动态 handler 场景。"""
    current_factory = logging.getLogRecordFactory()
    if getattr(current_factory, "_mailflow_redacting", False):
        return

    def redacting_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = current_factory(*args, **kwargs)
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return record

    redacting_factory._mailflow_redacting = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(redacting_factory)
