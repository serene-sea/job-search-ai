"""用真实 HTTP 路由检验岗位行为和两个登录账号的隔离。"""

from fastapi.testclient import TestClient

from backend.main import app
from backend.tests.test_auth import auth_db, write_headers  # noqa: F401  复用临时库夹具。


def write(client: TestClient, method: str, path: str, body: dict | None = None):
    return client.request(method, path, json=body or {}, headers=write_headers)


def login_as(client: TestClient, username: str) -> int:
    password = f"{username}-password-123"
    assert write(client, "POST", "/api/auth/register", {"username": username, "password": password}).status_code == 201
    assert write(client, "POST", "/api/auth/login", {"username": username, "password": password}).status_code == 200
    return client.get("/api/job-statuses").json()[0]["id"]


def job_body(status_id: int, **changes) -> dict:
    return {"company_name": "甲公司", "title": "Python 后端", "status_id": status_id, **changes}


def test_company_grouping_and_exact_status_filter(auth_db) -> None:
    with TestClient(app) as client:
        wanted_status = login_as(client, "alice")
        applied_status = next(item["id"] for item in client.get("/api/job-statuses").json() if item["name"] == "已投")
        first = write(client, "POST", "/api/jobs", job_body(wanted_status, requirements_text="会 SQL"))
        second = write(client, "POST", "/api/jobs", job_body(applied_status, notes="已提交"))
        assert first.status_code == second.status_code == 201
        assert first.json()["id"] != second.json()["id"]  # 同名岗位不自动合并。
        assert client.get("/api/jobs/companies").json() == [
            {"company_name": "甲公司", "total": 2}
        ]
        applied = client.get("/api/jobs", params={"company_name": "甲公司", "status_id": applied_status}).json()
        assert applied["total"] == 1
        assert applied["items"][0]["id"] == second.json()["id"]

        # 自定义状态的名字不被解析成“已投/未投”；筛选始终按状态编号。
        status = write(client, "PATCH", f"/api/job-statuses/{wanted_status}", {"name": "考虑中", "sort_order": 9})
        assert status.status_code == 200
        unchanged = client.get(f"/api/jobs/{first.json()['id']}").json()
        assert unchanged["status_name"] == "考虑中"
        assert unchanged["requirements_text"] == "会 SQL"

        changed = write(client, "PATCH", f"/api/jobs/{second.json()['id']}", {"status_id": wanted_status})
        assert changed.status_code == 200
        assert changed.json()["status_name"] == "考虑中"
        assert client.get("/api/jobs", params={"status_id": applied_status}).json()["total"] == 0


def test_two_users_cannot_read_write_or_attach_each_others_job_and_status(auth_db) -> None:
    with TestClient(app) as alice, TestClient(app) as bob:
        alice_status = login_as(alice, "alice")
        bob_status = login_as(bob, "bob")
        own = write(alice, "POST", "/api/jobs", job_body(alice_status))
        assert own.status_code == 201
        job_id = own.json()["id"]

        assert bob.get("/api/jobs").json()["total"] == 0
        assert bob.get("/api/jobs/companies").json() == []
        assert bob.get(f"/api/jobs/{job_id}").status_code == 404
        assert write(bob, "PATCH", f"/api/jobs/{job_id}", {"title": "篡改"}).status_code == 404
        assert write(bob, "DELETE", f"/api/jobs/{job_id}").status_code == 404
        assert write(bob, "POST", "/api/jobs", job_body(alice_status)).status_code == 404
        assert write(bob, "PATCH", f"/api/job-statuses/{alice_status}", {"name": "篡改"}).status_code == 404
        assert write(alice, "PATCH", f"/api/jobs/{job_id}", {"status_id": bob_status}).status_code == 404
        assert alice.get(f"/api/jobs/{job_id}").json()["title"] == "Python 后端"

        # Cookie 不存在或跨站写入时，请求在触及岗位数据前就被拒绝。
        with TestClient(app) as anonymous:
            assert anonymous.get("/api/jobs").status_code == 401
        assert alice.patch(f"/api/jobs/{job_id}", json={"title": "无来源头"}).status_code == 403


def test_status_management_and_delete(auth_db) -> None:
    with TestClient(app) as client:
        status_id = login_as(client, "alice")
        # 旧投递标记不再是接口字段，防止调用方继续制造第二份进度信息。
        assert write(client, "POST", "/api/jobs", job_body(status_id, has_applied=True)).status_code == 422
        new_status = write(client, "POST", "/api/job-statuses", {"name": "等待二面", "sort_order": 30})
        assert new_status.status_code == 201
        assert write(client, "POST", "/api/job-statuses", {"name": "等待二面", "sort_order": 31}).status_code == 409
        job = write(client, "POST", "/api/jobs", job_body(new_status.json()["id"]))
        assert job.status_code == 201
        job_id = job.json()["id"]
        assert write(client, "DELETE", f"/api/job-statuses/{new_status.json()['id']}").status_code == 409
        assert write(client, "PATCH", f"/api/jobs/{job_id}", {"applied_on": "2026-10-15"}).status_code == 422
        assert write(client, "PATCH", f"/api/jobs/{job_id}", {"source_url": "javascript:alert(1)"}).status_code == 422
        assert write(client, "DELETE", f"/api/jobs/{job_id}").status_code == 204
        assert write(client, "DELETE", f"/api/job-statuses/{new_status.json()['id']}").status_code == 204
        assert client.get(f"/api/jobs/{job_id}").status_code == 404
