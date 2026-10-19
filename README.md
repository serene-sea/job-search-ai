# 求职帮

用于记录求职岗位、维护个人资料，并在人工核对招聘要求后生成有依据的岗位报告。项目面向本地单用户或少量账号使用，界面由 Vue 3 构建，后端使用 FastAPI。

## 已实现

- 账号注册与登录：密码哈希、HttpOnly Cookie 会话，岗位和个人记录按登录用户隔离。
- 求职记录：一家公司可记录多条岗位；按公司与自定义状态查看、编辑岗位。公司目前按岗位中的公司名分组。
- 个人资料：教育、项目、技能、基本信息；简历支持 PDF、DOCX、TXT 临时提取，人工修订并确认后才参与分析，原文件不长期保存。
- 岗位报告：先从用户录入的招聘原文提取要求并人工核对，再把要求与本人记录对齐；服务端校验原文片段、资料快照版本和模型引用编号。
- 聊天：普通模式与结合个人资料模式、会话历史、SSE 流式回答；停止生成会请求服务端取消本机任务并记录中断状态。生成报告时输入的问题会在报告保存后作为独立聊天提问。

## 技术选择

- **MySQL + SQLAlchemy 2.x + Alembic**：管理岗位、状态、个人资料和会话的关系及迁移；接口按服务端登录用户过滤记录。
- **FastAPI + Pydantic**：实现鉴权、文件解析、业务接口、输入校验和 SSE。
- **Vue 3 + TypeScript + Vite**：实现岗位、资料、简历和统一聊天页面。
- **DeepSeek Chat Completions**：使用同一模型服务完成要求提取、证据对齐、报告撰写与聊天。模型不能执行 SQL；报告中的引用编号由服务端校验。

## 本地启动

需要 Python 3.12、MySQL 和符合 `frontend/package.json` 要求的 Node.js。先复制 `backend/.env.example` 为 `backend/.env`，填写自己的 `DATABASE_URL`。使用 AI 功能时再填写 `JOB_AI_API_KEY`；不要提交真实密钥。

从项目根目录运行：

```powershell
python -m pip install -r backend/requirements.txt
python -m alembic -c backend/alembic.ini upgrade head
python backend/main.py
```

另开终端：

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm run dev
```

打开 `http://localhost:5173/`。开发环境将 `/api` 代理到 `http://127.0.0.1:8000`。升级已有数据库前先备份；健康检查 `GET /api/health` 不依赖 MySQL。

## 检查

```powershell
python -m pytest backend/tests -q
cd frontend
pnpm run build
```

测试使用临时 SQLite 和假模型，不会调用真实 AI 服务。仓库不含 API Key、真实简历或用户数据库。

## 当前边界

这是本地作品，未提供公开在线演示。公司尚未独立建表，招聘详情只支持文本录入；受控 Agent、联网检索、自动投递和批量岗位推荐未实现。报告引用可追溯不等于模型判断一定正确，具体经历、招聘信息和建议仍需人工核对。流式取消按本地单进程实现，跨进程部署未处理。