
import asyncio
import os
import logging
from backend.utils.log_config import setup_logging

# 解决Windows上Playwright的NotImplementedError
# 策略设置已移至run.py以确保其在uvicorn启动前生效
# if os.name == 'nt':
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend import crud, schemas
from backend.database import SessionLocal, engine, get_db
from backend.auth import get_current_system_user
from backend.models import Base  # 导入Base以确保模型被FastAPI识别

# 导入路由模块
from backend.api import users
from backend.api import credentials
from backend.api import tasks

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Application startup: Initializing database and creating admin user if needed.")
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        admin_user = crud.get_system_user_by_username(db, username="admin")
        if not admin_user:
            admin_schema = schemas.SystemUserCreate(
                username="admin",
                phone_number="12345678910", # 示例手机号码，请在生产环境中更改
                password="Admin@123", # 示例密码，请在生产环境中更改
                passwordConfirm="Admin@123",
                is_active=True,  # 管理员用户默认激活
                is_approved=True # 管理员用户默认已审批
            )
            crud.create_system_user(db, admin_schema)
            logger.info("管理员用户 'admin' 已自动创建。")
        else:
            logger.info("管理员用户 'admin' 已存在。")
    except Exception as e:
        logger.error(f"创建管理员用户失败: {e}")
    finally:
        db.close()
    
# 将根路由 `/` 重定向到 `/login`
@app.get("/")
async def redirect_to_login():
    return RedirectResponse(url="/login")

# 提供登录页面
@app.get("/login", response_class=FileResponse)
async def serve_login_page():
    return "frontend/login.html"

# 提供主页 (index.html) - 用户登录后访问的页面
@app.get("/index", response_class=FileResponse) # 将主页挂载到 /index 路径
async def serve_index_page():
    return "frontend/index.html"

# 提供凭据设置页面
@app.get("/credentials-setup", response_class=FileResponse)
async def serve_credentials_setup_page():
    return "frontend/credentials_setup.html"

# 提供新的自动学习日志页面
@app.get("/auto-learn", response_class=FileResponse)
async def serve_auto_learn_page():
    return "frontend/auto-learn.html"

# 提供任务详情页面
@app.get("/task-detail.html", response_class=FileResponse)
async def serve_task_detail_page():
    return "frontend/task_detail.html"

# 从 /static 提供其他静态文件 (CSS, JS)
# app.mount("/static", StaticFiles(directory="frontend"), name="static")

# 分别挂载 CSS 和 JS 目录
app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")

@app.get("/logs", response_class=FileResponse)
async def serve_logs_page():
    return "frontend/logs.html"

@app.get("/admin", response_class=FileResponse)
async def serve_admin_page():
    return "frontend/admin.html"

# 注册 API 路由器
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(credentials.router, prefix="/api/credentials", tags=["credentials"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
logging.getLogger(__name__).info("Tasks router included successfully!")

# LearningWebsiteCredential, login, save_session, 和 start_watching 路由现在由 backend/api/ 处理