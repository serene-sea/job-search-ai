"""FastAPI 应用入口；后续业务路由在这里统一注册。"""

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # 直接执行 backend/main.py 时，也能找到项目根目录下的 backend 包。
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI

from backend.config import load_local_env
from backend.routers.analysis import router as analysis_router
from backend.routers.chat import router as chat_router
from backend.routers.auth import router as auth_router
from backend.routers.jobs import router as jobs_router
from backend.routers.history import router as history_router
from backend.routers.personal import router as personal_router
from backend.routers.resume import router as resume_router
from backend.routers.system import router as system_router

# 创建应用时读取本机配置，随后把登录和健康检查路由接进来。
load_local_env()
app = FastAPI(title="求职帮", version="0.1.0")
app.include_router(system_router)
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(history_router)
app.include_router(analysis_router)
app.include_router(chat_router)
app.include_router(personal_router)
app.include_router(resume_router)


if __name__ == "__main__":
    import uvicorn
    # 用模块路径找到 app，才能在本地改代码后自动重载。
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
