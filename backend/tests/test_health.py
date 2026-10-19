"""验证最小 HTTP 链路，避免把仅能导入模块误当作服务可用。"""

from fastapi.testclient import TestClient

from backend.main import app


def test_health_returns_expected_json() -> None:
    """健康接口返回固定内容，且不需要数据库或登录。"""
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
