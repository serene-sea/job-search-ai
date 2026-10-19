"""读取本机配置；终端里已设置的值优先。"""

from pathlib import Path

from dotenv import load_dotenv

LOCAL_ENV_FILE = Path(__file__).resolve().parent / ".env"


def load_local_env() -> None:
    """从 backend/.env 补齐缺少的环境变量，不覆盖终端设置。"""

    # 无论终端当前在哪个目录，都固定读取 backend/.env。
    load_dotenv(dotenv_path=LOCAL_ENV_FILE, override=False)
