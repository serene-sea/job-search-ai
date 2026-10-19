"""资料和技能的真实 HTTP 流程：保存、修改及两个账号互相隔离。"""

from fastapi.testclient import TestClient

from backend.main import app
from backend.tests.test_auth import auth_db, write_headers  # noqa: F401


def write(client: TestClient, method: str, path: str, body: dict):
    return client.request(method, path, json=body, headers=write_headers)


def login(client: TestClient, username: str) -> None:
    password = f"{username}-password-123"
    assert write(client, "POST", "/api/auth/register", {"username": username, "password": password}).status_code == 201
    assert write(client, "POST", "/api/auth/login", {"username": username, "password": password}).status_code == 200


def test_profile_skills_save_edit_and_isolation(auth_db) -> None:
    with TestClient(app) as alice, TestClient(app) as bob:
        login(alice, "alice")
        login(bob, "bob")

        assert bob.get("/api/profile").json()["school"] is None
        assert "birth_date" not in bob.get("/api/profile").json()
        assert write(alice, "PATCH", "/api/profile", {"birth_date": "2000-01-01"}).status_code == 422
        saved = write(alice, "PATCH", "/api/profile", {
            "school": "  某大学  ", "major": "网络空间安全", "graduation_year": 2027,
            "experience_text": "真实项目经历",
        })
        assert saved.status_code == 200
        assert alice.get("/api/profile").json()["school"] == "某大学"
        assert bob.get("/api/profile").json()["school"] is None
        assert write(alice, "PATCH", "/api/profile", {"school": "另一大学"}).json()["major"] == "网络空间安全"
        assert write(alice, "PATCH", "/api/profile", {"graduation_year": 1800}).status_code == 422

        skill = write(alice, "POST", "/api/skills", {
            "name": " MySQL ", "proficiency": 2, "importance": 5,
            "description": "会基础 SQL；缺索引实践",
        })
        assert skill.status_code == 201
        skill_id = skill.json()["id"]
        assert skill.json()["name"] == "MySQL"
        assert write(alice, "POST", "/api/skills", {
            "name": "MySQL", "proficiency": 3, "importance": 5,
        }).status_code == 409
        assert bob.get("/api/skills").json() == []
        assert bob.get(f"/api/skills/{skill_id}").status_code == 404
        assert write(bob, "PATCH", f"/api/skills/{skill_id}", {"name": "篡改"}).status_code == 404
        assert write(bob, "DELETE", f"/api/skills/{skill_id}", {}).status_code == 404
        assert write(alice, "PATCH", f"/api/skills/{skill_id}", {
            "proficiency": 3, "description": "增加事务实践",
        }).status_code == 200
        assert alice.get("/api/skills").json()[0]["proficiency"] == 3
        assert write(alice, "DELETE", f"/api/skills/{skill_id}", {}).status_code == 204
        assert alice.get("/api/skills").json() == []

        with TestClient(app) as anonymous:
            assert anonymous.get("/api/profile").status_code == 401
            assert anonymous.get("/api/skills").status_code == 401
        assert alice.patch("/api/profile", json={"school": "无来源头"}).status_code == 403
