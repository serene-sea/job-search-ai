"""模型服务的少量兼容参数；普通服务仍使用标准 Chat Completions 请求。"""

from urllib.parse import urlsplit

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"


def completion_options(base_url: str) -> dict:
    """DeepSeek 当前默认开启思考模式；本项目只消费最终回答，故显式关闭。"""

    if urlsplit(base_url).hostname == "api.deepseek.com":
        return {"thinking": {"type": "disabled"}}
    return {}
