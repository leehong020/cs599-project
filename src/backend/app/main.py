from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assistant_graph import router as assistant_graph_router
from app.api.auth import callback_router, router as auth_router
from app.api.calendar import router as calendar_router
from app.api.completeness import router as completeness_router
from app.api.files import router as files_router
from app.api.gmail import router as gmail_router
from app.api.health import router as health_router
from app.api.memory import router as memory_router
from app.api.settings import router as settings_router
from app.api.workflow import router as workflow_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    """创建 FastAPI 应用，并挂载当前阶段已经完成的后端能力。

    当前已挂载 SSE 聊天流、文件上传解析和长期记忆等路由。把应用构造
    放在函数里，能让单元测试便宜地创建干净 app，
    避免测试共享一个被全局状态污染的对象。
    """
    configure_logging()
    settings = get_settings()

    # 阶段 1 的 API 元信息保持简洁即可。真正面向用户的产品文案放在
    # Vue 前端里；这里的 title/version 主要服务 OpenAPI 和调试。
    app = FastAPI(
        title="Mailflow Agent API",
        version="0.1.0",
    )

    # CORS 只允许配置中的前端地址访问。后续接入 OAuth cookie 或带认证
    # 的请求后，这里就是浏览器侧安全边界之一，不能随便放开为任意来源。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_base_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 常规业务 API 统一挂在 /api 下。Google callback 例外使用根路径
    # `/gmail/auth/callback`，因为这个地址已经登记到 Google Cloud Console，
    # 必须和 `.env` 中的 GOOGLE_REDIRECT_URI 完全一致。
    app.include_router(health_router, prefix="/api")
    app.include_router(assistant_graph_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(calendar_router, prefix="/api")
    app.include_router(completeness_router, prefix="/api")
    app.include_router(files_router, prefix="/api")
    app.include_router(gmail_router, prefix="/api")
    app.include_router(memory_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(workflow_router, prefix="/api")
    app.include_router(callback_router)

    return app


# Uvicorn 通过 `app.main:app` 启动时会导入这个模块级对象。
app = create_app()
