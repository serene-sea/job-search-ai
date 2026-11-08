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
            if body.get("tools"):
                # Agent 的更新流会逐步给页面报进度，但一次模型请求本身可以是普通 JSON。
                # 两种格式都支持，才能测到 LangChain 真实的调用方式。
                if body.get("stream") is True:
                    self._agent_reply(body)
                else:
                    self._agent_json_reply(body)
            elif body.get("stream") is True:
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

    def _agent_reply(self, body: dict) -> None:
        """模拟一次工具决策和一次最终回答，只验证调用链，不给真实求职建议。"""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            tool_messages = [row for row in body["messages"] if row.get("role") == "tool"]
            if not tool_messages:
                offered = {row["function"]["name"] for row in body["tools"]}
                names = [name for name in ("read_current_job", "read_skills") if name in offered]
                if not names:
                    names = [next(iter(offered))]
                # 第一轮让模型“请求工具”；真正查数据库的是求职帮的工具函数。
                calls = [{"index": index, "id": f"fake-call-{index}", "type": "function",
                          "function": {"name": name, "arguments": "{}"}}
                         for index, name in enumerate(names)]
                self._agent_event({"tool_calls": calls}, "tool_calls")
            else:
                references = []
                for row in tool_messages:
                    data = json.loads(row["content"])
                    references.extend(item["id"] for item in data.get("records", []))
                cites = "、".join(f"[{item}]" for item in references[:2])
                answer = "这是本地模拟 Agent 回答，已通过只读工具查看" + (cites or "所选资料") + "；不评估岗位匹配度。"
                self._agent_event({"content": answer}, "stop")
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _agent_json_reply(self, body: dict) -> None:
        tool_messages = [row for row in body["messages"] if row.get("role") == "tool"]
        if not tool_messages:
            offered = {row["function"]["name"] for row in body["tools"]}
            names = [name for name in ("read_current_job", "read_skills") if name in offered]
            if not names:
                names = [next(iter(offered))]
            message = {"role": "assistant", "content": None, "tool_calls": [
                {"id": f"fake-call-{index}", "type": "function",
                 "function": {"name": name, "arguments": "{}"}}
                for index, name in enumerate(names)]}
            finish_reason = "tool_calls"
        else:
            references = []
            for row in tool_messages:
                data = json.loads(row["content"])
                references.extend(item["id"] for item in data.get("records", []))
            cites = "、".join(f"[{item}]" for item in references[:2])
            message = {"role": "assistant", "content":
                       "这是本地模拟 Agent 回答，已通过只读工具查看" + (cites or "所选资料") +
                       "；不评估岗位匹配度。"}
            finish_reason = "stop"
        response = {"id": "fake-agent", "object": "chat.completion", "created": 0,
                    "model": "local-fake", "choices": [{"index": 0, "message": message,
                                                      "finish_reason": finish_reason}]}
        payload = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _agent_event(self, delta: dict, finish_reason: str) -> None:
        event = {"id": "fake-agent", "object": "chat.completion.chunk", "created": 0,
                 "model": "local-fake", "choices": [{"index": 0, "delta": delta,
                                                   "finish_reason": finish_reason}]}
        self.wfile.write((f"data: {json.dumps(event, ensure_ascii=False)}\n\n").encode("utf-8"))
        self.wfile.flush()


if __name__ == "__main__":
    print("本地假模型监听 http://127.0.0.1:8765/v1；只用于模拟资料联调。", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8765), FakeModelHandler).serve_forever()
