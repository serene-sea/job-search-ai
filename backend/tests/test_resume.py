"""临时文件提取、文本确认与两个登录用户的数据边界。"""

from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend.main import app
from backend.tests.test_auth import auth_db, write_headers  # noqa: F401


def write(client: TestClient, method: str, path: str, body: dict):
    return client.request(method, path, json=body, headers=write_headers)


def login(client: TestClient, username: str) -> None:
    password = f"{username}-password-123"
    assert write(client, "POST", "/api/auth/register", {"username": username, "password": password}).status_code == 201
    assert write(client, "POST", "/api/auth/login", {"username": username, "password": password}).status_code == 200


def upload(client: TestClient, filename: str, content: bytes):
    return client.post("/api/resume/upload", files={"file": (filename, content)}, headers=write_headers)


def test_resume_text_upload_review_replace_and_isolation(auth_db) -> None:
    with TestClient(app) as alice, TestClient(app) as bob:
        login(alice, "alice")
        login(bob, "bob")

        first = upload(alice, "resume.txt", "Python 后端\n会 SQL".encode())
        assert first.status_code == 200
        assert first.json()["raw_extracted_text"] == "Python 后端\n会 SQL"
        assert first.json()["confirmed_at"] is None
        assert alice.get("/api/resume").json()["reviewed_text"] == "Python 后端\n会 SQL"
        assert bob.get("/api/resume").json() is None

        assert write(alice, "POST", "/api/resume/confirm", {}).json()["confirmed_at"] is not None
        edited = write(alice, "PATCH", "/api/resume", {"reviewed_text": "Python 后端\n会基础 SQL"})
        assert edited.status_code == 200
        assert edited.json()["confirmed_at"] is None
        assert edited.json()["raw_extracted_text"] == "Python 后端\n会 SQL"
        assert alice.get("/api/resume").json()["reviewed_text"] == "Python 后端\n会基础 SQL"

        assert write(alice, "POST", "/api/resume/confirm", {}).json()["confirmed_at"] is not None

        doc = Document()
        doc.add_paragraph("真实项目经历")
        file = BytesIO()
        doc.save(file)
        replaced = upload(alice, "new.docx", file.getvalue())
        assert replaced.status_code == 200
        assert "真实项目经历" in replaced.json()["raw_extracted_text"]
        assert replaced.json()["confirmed_at"] is None
        assert bob.get("/api/resume").json() is None

        assert write(bob, "PATCH", "/api/resume", {"reviewed_text": "Bob 的简历"}).status_code == 200
        assert bob.get("/api/resume").json()["raw_extracted_text"] == ""
        assert alice.get("/api/resume").json()["reviewed_text"] != "Bob 的简历"
        assert write(bob, "DELETE", "/api/resume", {}).status_code == 204
        assert bob.get("/api/resume").json() is None
        assert alice.get("/api/resume").json()["source_filename"] == "new.docx"


def test_pdf_without_text_manual_paste_and_upload_errors(auth_db) -> None:
    with TestClient(app) as client:
        login(client, "alice")
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buffer = BytesIO()
        writer.write(buffer)
        result = upload(client, "scan.pdf", buffer.getvalue())
        assert result.status_code == 200
        assert result.json()["raw_extracted_text"] == ""
        assert write(client, "POST", "/api/resume/confirm", {}).status_code == 422
        assert write(client, "PATCH", "/api/resume", {"reviewed_text": "手动核对的文字"}).status_code == 200
        assert write(client, "POST", "/api/resume/confirm", {}).json()["confirmed_at"] is not None
        assert upload(client, "old.doc", b"old").status_code == 415
        assert upload(client, "fake.pdf", b"not-pdf").status_code == 422
        assert upload(client, "large.txt", b"a" * (10 * 1024 * 1024 + 1)).status_code == 413
        assert client.post("/api/resume/upload", files={"file": ("x.txt", b"abc")}).status_code == 403
        with TestClient(app) as anonymous:
            assert anonymous.get("/api/resume").status_code == 401
