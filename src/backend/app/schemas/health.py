from pydantic import BaseModel


class HealthResponse(BaseModel):
    """健康检查响应。

    前端阶段 1 用它验证 API 是否可用，并显示当前后端环境。
    """

    status: str
    environment: str
