"""只供本机联调的假模型服务；不访问真实模型，也不保存请求内容。"""

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeModelHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        # 请求中可能含个人资料，故不输出路径之外的正文或请求头。
        return

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 100_000:
                raise ValueError("请求大小无效")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("请求格式无效")
            if body.get("stream") is True:
                self._stream_reply()
            else:
                self._json_reply(body)
        except (ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError):
            self.send_error(400)

    def _json_reply(self, body: dict) -> None:
        # 第一步只回传招聘原文中的连续片段；第二步一律标记“证据不足”。
        # 这里没有语义分析能力，目的只是验证页面、API 与证据校验的调用链。
        messages = body["messages"]
        data = json.loads(messages[-1]["content"])
        if "requirements_text" in data:
            text = data["requirements_text"].strip()
            quote = next((line.strip()[:350] for line in text.splitlines() if len(line.strip()) >= 2), "")
            result = {"items": [{"quote": quote, "priority": "unspecified"}]} if quote else {"items": []}
        else:
            result = {"items": [
                {"requirement_index": row["index"], "status": "no_evidence", "evidence_ids": [],
                 "reason": "本地假模型不评估证据", "next_step": "接入真实模型后人工核对"}
                for row in data["requirements"]
            ]}
        payload = json.dumps({"choices": [{"message": {"content": json.dumps(result, ensure_ascii=False)}}]},
                             ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _stream_reply(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        # 故意分批发，便于在浏览器测试“停止生成”是否关闭服务端上游连接。
        try:
            for index in range(35):
                chunk = "这是本地模拟回答，仅用于检查流式显示与停止功能。" if index == 0 else "模拟片段。"
                event = {"choices": [{"delta": {"content": chunk}}]}
                self.wfile.write((f"data: {json.dumps(event, ensure_ascii=False)}\n\n").encode("utf-8"))
                self.wfile.flush()
                time.sleep(0.12)
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # 停止生成会关闭连接；假模型也随之停止发送。
            pass


if __name__ == "__main__":
    print("本地假模型监听 http://127.0.0.1:8765/v1；只用于模拟资料联调。", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8765), FakeModelHandler).serve_forever()
