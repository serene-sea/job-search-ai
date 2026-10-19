"""与业务数据无关的系统接口。"""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    """返回后端存活状态，供前端连通性检查使用。

    这里不查询 MySQL，因此在我们共同设计数据库之前也能验证前后端链路。
    它只证明 HTTP 服务可响应，不代表登录、数据库或 LLM 已可用。
    """
    return {"status": "ok"}
