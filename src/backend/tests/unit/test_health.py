from fastapi.testclient import TestClient

from app.main import create_app


def test_health_check_returns_ok() -> None:
    # 这是阶段 1 的冒烟测试，故意走真实 FastAPI app factory。
    # 它能在 OAuth 和聊天路由接入前，提前发现路由挂载、配置加载、
    # SQLite 连接这些基础设施问题。
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
