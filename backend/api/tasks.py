from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends, status, Query, Request # 导入 Request
from sqlalchemy.orm import Session
from typing import Optional, List
import asyncio
import logging
import json # 导入 json 模块

from backend import crud, schemas, models # 导入 models
from backend.database import get_db, SessionLocal # 导入 SessionLocal
from backend.utils import auto_watcher_runner as auto_watcher_utils
from backend.auth import get_current_system_user, verify_access_token # 导入 verify_access_token
from backend.schemas import SystemUserOut, LaunchWebRequest
from backend.utils.log_config import _websocket_log_queue # 导入全局日志队列
from backend.context import RequestContext, get_request_context # 导入 RequestContext 和 get_request_context

router = APIRouter()

# 活跃的WebSocket连接，用于实时日志 (现在是所有连接的集合)
active_websocket_connections: List[WebSocket] = []

# 实时日志广播任务的标志
log_broadcast_task = None

async def broadcast_logs():
    """ 后台任务：持续从队列中读取日志并广播给所有活跃的WebSocket连接。 """
    global active_websocket_connections
    logger = logging.getLogger(__name__)
    last_processed_index = 0
    while True:
        try:
            # 检查是否有新的日志
            if len(_websocket_log_queue) > last_processed_index:
                new_logs = list(_websocket_log_queue)[last_processed_index:]
                for log_data in new_logs:
                    for websocket in list(active_websocket_connections):
                        try:
                            await websocket.send_text(json.dumps(log_data)) # 发送 JSON 字符串
                        except WebSocketDisconnect:
                            logger.warning(
                                "[WebSocket Broadcaster] 检测到断开连接，移除WebSocket。",
                                extra={"user_id": log_data.get('user_id'), "username": log_data.get('username'), "ip_address": log_data.get('ip_address')}
                            )
                last_processed_index = len(_websocket_log_queue)
            await asyncio.sleep(0.1) # 短暂休眠，避免CPU空转
        except Exception as e:
            logger.error(
                f"[WebSocket Broadcaster] 发生未预期的错误: {e}",
                extra={"user_id": None, "username": None, "ip_address": None} # 广播任务的通用错误，无法可靠获取用户上下文
            )
            await asyncio.sleep(1) # 错误时休眠长一点

@router.websocket("/ws/logs")
async def websocket_endpoint(
    websocket: WebSocket, 
    token: str = Query(...), # 从查询参数中获取 token
    db: Session = Depends(get_db) # 获取数据库会话
):
    await websocket.accept()

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = None
    user_id = None
    username = None
    ip_address = None # 初始化

    # 将整个逻辑包裹在一个大的 try-except-finally 块中
    try:
        # 尝试从 WebSocket scope 获取 IP
        if "client" in websocket.scope and websocket.scope["client"] is not None:
            ip_address = websocket.scope["client"][0] # (host, port)
        token_data = verify_access_token(token, credentials_exception) # 验证 token
        # 尝试根据用户名或手机号找到用户
        if token_data.learning_username: # 将 username 修改为 learning_username
            user = crud.get_system_user_by_username(db, username=token_data.learning_username) # 将 username 修改为 learning_username
        elif token_data.phone_number:
            user = crud.get_system_user_by_phone_number(db, phone_number=token_data.phone_number)
        
        if user is None:
            raise credentials_exception
        
        user_id = user.id
        username = user.username
        
        # 将当前WebSocket添加到活跃连接列表
        active_websocket_connections.append(websocket)
        logging.getLogger(__name__).info(
            f"用户 {user.username} 已连接到系统日志 WebSocket。总连接数: {len(active_websocket_connections)}",
            extra={"user_id": user_id, "username": username, "ip_address": ip_address}
        )

        # 启动日志广播任务（如果尚未启动）
        global log_broadcast_task
        if log_broadcast_task is None or log_broadcast_task.done():
            log_broadcast_task = asyncio.create_task(broadcast_logs())
            logging.getLogger(__name__).info(
                "系统日志广播任务已启动。",
                extra={"user_id": user_id, "username": username, "ip_address": ip_address}
            )

        # 发送历史日志（从数据库获取）
        # 可以限制条数，例如最近100条
        # historical_logs = db.query(models.LogEntry).order_by(models.LogEntry.timestamp.asc()).limit(100).all()
        # for log_entry_obj in historical_logs:
        #     log_data = {
        #         "timestamp": log_entry_obj.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        #         "level": log_entry_obj.level,
        #         "message": log_entry_obj.message, # 直接使用数据库中存储的消息，因为它现在应该已经是预格式化好的
        #         "user_id": log_entry_obj.user_id,
        #         "username": log_entry_obj.user.username if log_entry_obj.user else None,
        #         "ip_address": log_entry_obj.ip_address
        #     }
        #     await websocket.send_text(json.dumps(log_data)) # 发送 JSON 字符串

        # 保持连接活跃，直到客户端断开
        while True:
            # 保持连接，可以监听ping/pong或简单地等待断开
            await websocket.receive_text() # 只是为了保持连接，实际不处理接收到的消息

    except HTTPException as e:
        logging.getLogger(__name__).warning(
            f"日志WebSocket认证失败: {e.detail}",
            extra={"user_id": user_id, "username": username, "ip_address": ip_address} # 认证失败时尝试提供已有信息
        )
        await websocket.send_text(f"认证失败: {e.detail}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION) # 1008 表示策略违反，例如认证失败
    except WebSocketDisconnect:
        logging.getLogger(__name__).info(
            f"用户 {user.username if 'user' in locals() else '未知'} 已断开系统日志 WebSocket 连接。总连接数: {len(active_websocket_connections)}",
            extra={"user_id": user_id, "username": username, "ip_address": ip_address}
        )
    except Exception as e:
        logging.getLogger(__name__).error(
            f"日志WebSocket发生错误: {e}",
            extra={"user_id": user_id, "username": username, "ip_address": ip_address}
        )
        # 尝试发送错误消息，但连接可能已断开
        try:
            await websocket.send_text(f"内部错误: {e}")
        except:
            pass
    finally:
        # 从活跃连接列表中移除
        if websocket in active_websocket_connections:
            active_websocket_connections.remove(websocket)
        logging.getLogger(__name__).info(
            f"WebSocket连接已清理。当前活跃连接数: {len(active_websocket_connections)}",
            extra={"user_id": user_id, "username": username, "ip_address": ip_address}
        )

@router.get("/test")
async def test_tasks_router():
    return {"message": "Tasks router is working!"}

@router.post("/launch-web-for-login/{credential_id}") # 新增：通过凭据ID启动自动化流程
async def launch_web_for_login(
    credential_id: int,
    request: schemas.LaunchWebRequest, # 使用新的请求体模型
    background_tasks: BackgroundTasks,
    request_context: RequestContext = Depends(get_request_context), # 获取请求上下文
    db: Session = Depends(get_db)
):
    user_id = request_context.user_id
    username = request_context.username # 获取用户名
    ip_address = request_context.ip_address

    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户未认证。")

    # 使用带有用户ID、用户名和IP的日志记录
    auto_watcher_utils.console_log(f"收到启动Web登录请求，凭据ID: {credential_id}。", user_id, username, ip_address, level=logging.INFO)

    credential = crud.get_learning_website_credential(db, credential_id=credential_id, system_user_id=user_id)
    if not credential:
        auto_watcher_utils.console_log(f"未找到凭据 ID {credential_id} 或无权限访问。", user_id, username, ip_address, level=logging.WARNING)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定的凭据或无权限访问。")

    if not credential.website_url:
        auto_watcher_utils.console_log(f"凭据 ID {credential_id} 未设置网站URL。", user_id, username, ip_address, level=logging.WARNING)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="学习网站URL未设置。请先在凭据设置页面设置。")
    
    # 启动浏览器并尝试登录
    try:
        # 将启动浏览器操作作为后台任务运行
        background_tasks.add_task(
            auto_watcher_utils.launch_browser_for_user_login,
            user_id,
            credential.website_url,
            credential.learning_username,
            credential.learning_password,
            headless=request.headless, # 从请求体中获取headless状态
            ip_address=ip_address, # 明确作为关键字参数
            system_username=username # 明确作为关键字参数
        )
        auto_watcher_utils.console_log(f"已将启动浏览器任务添加到后台。", user_id, username, ip_address, level=logging.INFO)
        return {"message": "浏览器启动任务已在后台启动。"}
    except Exception as e:
        auto_watcher_utils.console_log(f"启动浏览器时发生错误: {e}", user_id, username, ip_address, level=logging.ERROR)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"启动浏览器失败: {e}")

@router.post("/start-auto-watching") # 启动视频观看自动化任务
async def start_watching(
    background_tasks: BackgroundTasks, 
    current_user: SystemUserOut = Depends(get_current_system_user),
    request_context: RequestContext = Depends(get_request_context), # 获取请求上下文
    db: Session = Depends(get_db) # 重新添加 db 参数
):
    """ 启动视频观看自动化任务，使用当前系统用户最近一个已登录的浏览器会话。 """
    user_id = request_context.user_id
    system_username = request_context.username # 获取系统用户名
    ip_address = request_context.ip_address

    # auto_watcher_utils.console_log("Received start-watching request!") # 已经有下面的更详细日志，这里可以删除

    # 获取用户的学习网站凭据，以获取固定的视频列表URL
    credential = crud.get_learning_website_credential_by_user(db, system_user_id=user_id)
    if not credential or not credential.video_list_url:
        auto_watcher_utils.console_log(f"没有找到学习网站凭据或未设置视频列表URL。", user_id, system_username, ip_address, level=logging.WARNING)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有找到学习网站凭据或未设置视频列表URL。请先在凭据设置页面添加并设置。")

    # 从活跃的浏览器实例中获取当前会话的 cookies
    # 这里不再使用 cookies，而是直接传递 page 实例
    page = auto_watcher_utils._active_browser_pages.get(user_id)
    if not page:
        auto_watcher_utils.console_log(f"没有找到活跃的浏览器会话。", user_id, system_username, ip_address, level=logging.WARNING)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有找到活跃的浏览器会话。请先点击‘打开学习网站’按钮。") # 修正错误消息

    # 在后台启动视频观看任务，不阻塞 FastAPI 响应
    background_tasks.add_task(
        auto_watcher_utils.run_auto_watcher, 
        user_id, # 传递 user_id
        page, # 传递 page 实例
        credential.id, # 传递凭据ID
        ip_address, # 传递 ip_address
        system_username # 传递 system_username
    )

    return {"message": "学习任务已在后台启动。"}

@router.get("/{task_id}", response_model=schemas.LearningTaskDetail) # 新增：获取单个任务详情
async def get_task_detail(
    task_id: int,
    current_user: SystemUserOut = Depends(get_current_system_user),
    db: Session = Depends(get_db)
):
    """ 获取单个学习任务的详细信息，包括其关联的视频列表。 """
    user_id = current_user.id
    
    # 获取任务，并通过 credential_id 确保任务属于当前用户
    db_task = crud.get_learning_task(db, task_id=task_id)
    if not db_task or db_task.credential.system_user_id != user_id: # 检查任务是否属于当前用户
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定的任务或无权限访问。")
        
    return db_task

@router.get("/credentials/{credential_id}/tasks", response_model=List[schemas.LearningTaskDetail]) # 新增：获取某个凭据下的所有任务详情
async def get_tasks_for_credential(
    credential_id: int,
    current_user: SystemUserOut = Depends(get_current_system_user),
    db: Session = Depends(get_db)
):
    """ 获取某个学习网站凭据下的所有学习任务详情，包括每个任务关联的视频列表。 """
    user_id = current_user.id
    
    # 验证凭据是否存在且属于当前用户
    db_credential = crud.get_learning_website_credential(db, credential_id=credential_id, system_user_id=user_id)
    if not db_credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定的凭据或无权限访问。")

    tasks = crud.get_learning_tasks_by_credential_id_with_videos(db, credential_id=credential_id)
    
    return tasks

@router.post("/close-user-browser")
async def close_browser(
    current_user: SystemUserOut = Depends(get_current_system_user),
    request_context: RequestContext = Depends(get_request_context) # 获取请求上下文
):
    user_id = request_context.user_id
    username = request_context.username # 获取用户名
    ip_address = request_context.ip_address
    
    auto_watcher_utils.console_log(f"收到关闭浏览器请求。", user_id, username, ip_address, level=logging.INFO)
    await auto_watcher_utils.close_browser_for_user(user_id, username, ip_address)
    return {"message": "浏览器已关闭。"}

@router.post("/stop-auto-watching") # 新增路由：停止自动化学习任务并关闭浏览器
async def stop_auto_watching(
    background_tasks: BackgroundTasks, # 移动到前面
    current_user: SystemUserOut = Depends(get_current_system_user),
    request_context: RequestContext = Depends(get_request_context) # 获取请求上下文
):
    user_id = request_context.user_id
    username = request_context.username # 获取用户名
    ip_address = request_context.ip_address

    logging.getLogger(__name__).info("Received stop-auto-watching request!")

    try:
        # 发送停止请求的日志
        await auto_watcher_utils.send_log_to_queue(f"收到停止请求，正在停止自动化任务。", user_id, username, ip_address)
        await auto_watcher_utils.stop_auto_watcher_for_user(user_id, username, ip_address) # 发送停止信号给自动化任务
        await auto_watcher_utils.send_log_to_queue(f"正在返回上一页并准备关闭浏览器。", user_id, username, ip_address)
        # 将返回上一页并关闭浏览器的操作放到后台任务中，避免阻塞API响应
        # background_tasks.add_task(auto_watcher_utils.return_to_previous_page_and_close, user_id)
        return {"message": "停止学习任务请求已发送，浏览器将在返回页面后关闭。"}
    except Exception as e:
        logging.getLogger(__name__).error(f"停止观看任务时捕获到异常: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"停止观看任务失败: {e}")