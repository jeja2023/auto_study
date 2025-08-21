from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Annotated


from backend import crud, models
from backend.database import get_db
from backend.schemas import LearningWebsiteCredentialCreate, LearningWebsiteCredential, SystemUserOut # 修正导入
from backend.auth import get_current_system_user
from backend.utils import auto_watcher_runner as auto_watcher_utils # 导入自动化运行工具
from backend.utils.auto_watcher_runner import console_log # 修正：从 auto_watcher_runner 导入 console_log
from backend import schemas # 导入 schemas

router = APIRouter()

@router.get("/test-credentials")
async def test_credentials_router():
    return {"message": "Credentials router is working!"}

@router.post("/", response_model=LearningWebsiteCredential) # 用于添加或更新用户网站凭据
async def add_learning_website_credential(
    credential: LearningWebsiteCredentialCreate, 
    current_user: SystemUserOut = Depends(get_current_system_user), # 依赖系统用户认证
    db: Session = Depends(get_db)
):
    """ 添加或更新当前系统用户在学习网站的凭据（网站URL和视频列表URL）。 """
    # 不再需要密码验证，因为密码不再存储在后端
    # if credential.password != credential.password_confirm:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="两次输入的密码不一致！")

    db_credential = crud.get_learning_website_credential_by_website_url_and_user(db, current_user.id, credential.website_url)
    if db_credential:
        # 更新现有凭据
        db_credential.website_name = credential.website_name # 新增：更新网站名称
        db_credential.task_name = credential.task_name # 新增：更新任务名称
        db_credential.learning_username = credential.learning_username
        db_credential.phone_number = credential.phone_number
        db_credential.video_list_url = credential.video_list_url
        db_credential.learning_password = credential.learning_password # 新增：更新学习网站密码
        db.commit()
        db.refresh(db_credential)
        return db_credential
    else:
        # 创建新凭据
        return crud.create_learning_website_credential(db=db, system_user_id=current_user.id, credential=credential)

@router.get("/all", response_model=list[LearningWebsiteCredential]) # 这是一个获取所有凭据的路由
async def get_all_learning_website_credentials(
    current_user: Annotated[models.SystemUser, Depends(get_current_system_user)],
    db: Session = Depends(get_db),
):
    """ 获取当前用户的所有学习网站凭据。 """
    console_log(f"用户 {current_user.id}：尝试获取所有学习网站凭据列表。")
    credentials = crud.get_all_learning_website_credentials_by_user_id(db, system_user_id=current_user.id)
    # 移除404判断，直接返回凭据列表（可能为空）
    # if not credentials:
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到学习网站凭据")
    console_log(f"用户 {current_user.id}：成功获取 {len(credentials)} 条学习网站凭据。")
    return credentials

@router.get("/{credential_id}", response_model=LearningWebsiteCredential) # 新增：获取单个凭据详情
async def get_learning_website_credential_detail(
    credential_id: int,
    current_user: Annotated[models.SystemUser, Depends(get_current_system_user)],
    db: Session = Depends(get_db),
):
    """ 获取单个学习网站凭据的详细信息。 """
    db_credential = crud.get_learning_website_credential(db, credential_id=credential_id, system_user_id=current_user.id)
    if not db_credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定的学习网站凭据或无权限访问。")
    return db_credential

@router.delete("/{credential_id}", response_model=dict)
async def delete_learning_website_credential(
    credential_id: int,
    current_user: Annotated[models.SystemUser, Depends(get_current_system_user)],
    db: Session = Depends(get_db),
):
    console_log(f"用户 {current_user.id}：尝试删除学习网站凭据，ID: {credential_id}。")
    success = crud.delete_learning_website_credential(db, credential_id=credential_id, system_user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="未找到或无权限删除该凭据")
    console_log(f"用户 {current_user.id}：成功删除凭据，ID: {credential_id}。")
    return {"message": "凭据删除成功"}

@router.post("/launch-web-for-login/{credential_id}", response_model=dict)
async def launch_web_for_login(
    credential_id: int, # 新增 credential_id 参数
    current_user: Annotated[models.SystemUser, Depends(get_current_system_user)],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    console_log(f"用户 {current_user.id}：尝试通过凭据 ID {credential_id} 启动浏览器。")
    db_credential = crud.get_learning_website_credential(db, credential_id=credential_id, system_user_id=current_user.id)
    if not db_credential:
        raise HTTPException(status_code=404, detail="未找到指定的学习网站凭据")

    website_url = db_credential.website_url
    learning_username = db_credential.learning_username
    learning_password = db_credential.learning_password

    console_log("进入 launch_web_for_login 函数", current_user.id)
    console_log("尝试获取用户凭据...", current_user.id)
    # 这里不再从请求体获取，而是从数据库中加载
    # website_url = credential.website_url 

    console_log(f"成功获取凭据。网站URL: {website_url}", current_user.id)
    console_log("尝试启动浏览器...", current_user.id)

    try:
        # 启动浏览器并执行自动登录和初始导航
        page = await auto_watcher_utils.launch_browser_for_user_login(
            current_user.id, website_url, learning_username, learning_password
        )
        console_log("浏览器启动成功，返回响应。", current_user.id)
        # 将自动化任务添加到后台任务
        background_tasks.add_task(
            auto_watcher_utils.run_auto_watcher,
            user_id=current_user.id,
            page=page, # 传递活跃的 page 对象
            credential_id=credential_id # 传递凭据 ID
        )
        console_log(f"用户 {current_user.id}：浏览器已打开并完成登录，正在自动开始学习任务...", current_user.id)
        return {"message": "浏览器已打开并完成登录，正在自动开始学习任务。"}
    except Exception as e:
        console_log(f"启动浏览器失败: {e}", current_user.id)
        raise HTTPException(status_code=500, detail=f"启动浏览器失败: {e}")

@router.post("/close-user-browser") # 新增路由：关闭用户浏览器实例
async def close_user_browser(
    current_user: SystemUserOut = Depends(get_current_system_user) # 修正类型提示
):
    """ 关闭当前系统用户的浏览器实例。 """
    try:
        await auto_watcher_utils.close_browser_for_user(current_user.id)
        return {"message": "浏览器已关闭。"}
    except Exception as e:
        console_log(f"关闭浏览器失败: {e}", current_user.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"关闭浏览器失败: {e}")

@router.post("/view-learning-password/{credential_id}", response_model=dict)
async def view_learning_password(
    credential_id: int,
    system_user_credentials: schemas.SystemUserCredentials, # 接收系统用户名和密码
    current_user: Annotated[models.SystemUser, Depends(get_current_system_user)],
    db: Session = Depends(get_db),
):
    """ 安全地获取学习网站密码，需要验证系统用户密码。 """
    console_log(f"用户 {current_user.id}：尝试查看凭据 ID {credential_id} 的学习网站密码。", current_user.id)

    # 1. 验证 credential_id 是否属于当前用户
    db_credential = crud.get_learning_website_credential(db, credential_id=credential_id, system_user_id=current_user.id)
    if not db_credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定的学习网站凭据或无权限查看。")

    # 2. 验证提供的系统密码是否与当前登录用户匹配且正确
    # 不再需要通过用户名获取用户，直接使用 current_user 对象
    if not crud.verify_password(system_user_credentials.password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="系统密码不正确。")

    # 3. 如果验证成功，返回学习网站密码
    learning_password = db_credential.learning_password
    if not learning_password:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="学习网站密码未设置。")
    
    console_log(f"用户 {current_user.id}：成功查看凭据 ID {credential_id} 的学习网站密码。", current_user.id)
    return {"learning_password": learning_password}