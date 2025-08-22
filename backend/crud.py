from sqlalchemy.orm import Session, relationship, joinedload
from backend import models, schemas
import bcrypt # 直接导入bcrypt
from typing import Optional

def get_password_hash(password: str):
    """ 对密码进行哈希处理 """
    # 生成盐并哈希密码
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str):
    """ 验证明文密码和哈希密码是否匹配 """
    # 验证密码
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# --- 系统用户 (SystemUser) CRUD 操作 ---
def get_system_user_by_username(db: Session, username: str):
    """ 根据用户名获取系统用户 """
    return db.query(models.SystemUser).filter(models.SystemUser.username == username).first()

def get_system_user_by_phone_number(db: Session, phone_number: str):
    """ 根据手机号码获取系统用户 """
    return db.query(models.SystemUser).filter(models.SystemUser.phone_number == phone_number).first()

def get_system_user_by_username_or_phone(db: Session, username_or_phone: str):
    """ 根据用户名或手机号码获取系统用户 """
    # 检查是否是手机号码
    if username_or_phone.isdigit() and len(username_or_phone) == 11: # 假设中国手机号码为11位数字
        return get_system_user_by_phone_number(db, username_or_phone)
    else:
        return get_system_user_by_username(db, username_or_phone)

def create_system_user(db: Session, user: schemas.SystemUserCreate):
    """ 创建一个新的系统用户 """
    hashed_password = get_password_hash(user.password)
    db_user = models.SystemUser(
        username=user.username,
        phone_number=user.phone_number,
        hashed_password=hashed_password,
        is_active=user.is_active, # 从 schema 获取
        is_approved=user.is_approved # 从 schema 获取
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_system_user(db: Session, user_id: int):
    """ 根据 ID 获取系统用户 """
    return db.query(models.SystemUser).filter(models.SystemUser.id == user_id).first()

def get_unapproved_system_users(db: Session):
    """ 获取所有未审批的系统用户 """
    return db.query(models.SystemUser).filter(models.SystemUser.is_approved == False).all()

def approve_system_user(db: Session, user_id: int):
    """ 审批指定ID的系统用户 """
    db_user = db.query(models.SystemUser).filter(models.SystemUser.id == user_id).first()
    if db_user:
        db_user.is_approved = True
        db.commit()
        db.refresh(db_user)
        return db_user
    return None

# --- 学习网站凭据 (LearningWebsiteCredential) CRUD 操作 ---
def get_learning_website_credential_by_website_url_and_user(db: Session, system_user_id: int, website_url: str):
    """ 根据系统用户ID和网站 URL 获取学习网站凭据 """
    return db.query(models.LearningWebsiteCredential).filter(
        models.LearningWebsiteCredential.system_user_id == system_user_id,
        models.LearningWebsiteCredential.website_url == website_url
    ).first()

def get_learning_website_credential_by_user(db: Session, system_user_id: int):
    """ 根据系统用户ID获取其学习网站凭据（假设每个用户只有一个） """
    return db.query(models.LearningWebsiteCredential).filter(
        models.LearningWebsiteCredential.system_user_id == system_user_id
    ).first()

def get_all_learning_website_credentials_by_user_id(db: Session, system_user_id: int):
    """ 获取特定系统用户的所有学习网站凭据 """
    # 使用 joinedload 预加载 related tasks 和 videos
    return db.query(models.LearningWebsiteCredential).options(joinedload(models.LearningWebsiteCredential.tasks)).filter(
        models.LearningWebsiteCredential.system_user_id == system_user_id
    ).all()

def create_learning_website_credential(db: Session, system_user_id: int, credential: schemas.LearningWebsiteCredentialCreate):
    """ 为特定系统用户创建一个新的学习网站凭据 """
    db_credential = models.LearningWebsiteCredential(
        system_user_id=system_user_id,
        website_url=credential.website_url,
        website_name=credential.website_name,
        learning_username=credential.learning_username,
        # 移除 phone_number
        learning_password=credential.learning_password,
    )
    db.add(db_credential)
    db.commit()
    db.refresh(db_credential)
    return db_credential

def get_learning_website_credential(db: Session, credential_id: int, system_user_id: int):
    """ 根据 ID 和系统用户ID获取学习网站凭据 """
    return db.query(models.LearningWebsiteCredential).options(joinedload(models.LearningWebsiteCredential.tasks)).filter(
        models.LearningWebsiteCredential.id == credential_id,
        models.LearningWebsiteCredential.system_user_id == system_user_id
    ).first()

def get_learning_website_credential_by_username_or_phone_and_user(db: Session, system_user_id: int, website_url: str, username: str = None, phone_number: str = None):
    """ 根据系统用户ID、网站URL和用户名或手机号获取学习网站凭据 """
    query = db.query(models.LearningWebsiteCredential).filter(
        models.LearningWebsiteCredential.system_user_id == system_user_id,
        models.LearningWebsiteCredential.website_url == website_url
    )
    if username:
        query = query.filter(models.LearningWebsiteCredential.learning_username == username) # 修改为 learning_username
    elif phone_number:
        query = query.filter(models.LearningWebsiteCredential.phone_number == phone_number)
    return query.first()

def delete_learning_website_credential(db: Session, credential_id: int, system_user_id: int):
    """ 删除指定ID的学习网站凭据，并确保属于当前系统用户 """
    db_credential = db.query(models.LearningWebsiteCredential).filter(
        models.LearningWebsiteCredential.id == credential_id,
        models.LearningWebsiteCredential.system_user_id == system_user_id
    ).first()
    if db_credential:
        db.delete(db_credential)
        db.commit()
        return True
    return False

# --- 学习任务 (LearningTask) CRUD 操作 ---
def get_learning_task(db: Session, task_id: int, credential_id: int = None):
    """ 根据任务ID和可选的凭据ID获取学习任务及其所有视频 """
    query = db.query(models.LearningTask).options(joinedload(models.LearningTask.videos))
    
    if task_id is not None: # 确保 task_id 有值
        query = query.filter(models.LearningTask.id == task_id)
    
    if credential_id is not None: # credential_id 现在是可选的
        query = query.filter(models.LearningTask.credential_id == credential_id)
        
    return query.first()

def get_learning_tasks_by_credential_id(db: Session, credential_id: int):
    """ 根据凭据ID获取所有学习任务 """
    return db.query(models.LearningTask).filter(
        models.LearningTask.credential_id == credential_id
    ).options(relationship("videos")).all()

def get_learning_task_by_name_and_credential(db: Session, credential_id: int, task_name: str):
    """ 根据凭据ID和任务名称获取学习任务 """
    return db.query(models.LearningTask).filter(
        models.LearningTask.credential_id == credential_id,
        models.LearningTask.task_name == task_name
    ).first()

def create_learning_task(
    db: Session, task: schemas.LearningTaskCreate, credential_id: int
):
    """ 创建新的学习任务 """
    # 如果 study_hours 为 "0" 或空字符串，则设置为 None
    study_hours_to_save = task.study_hours if task.study_hours and task.study_hours != "0" else None

    db_task = models.LearningTask(
        credential_id=credential_id,
        task_name=task.task_name,
        task_url=task.task_url,
        study_hours=study_hours_to_save, # 保存学时
        current_progress=task.current_progress,
        is_completed=task.is_completed,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def get_learning_tasks_by_credential_id_with_videos(db: Session, credential_id: int):
    """ 根据凭据ID获取所有学习任务及其关联视频 """
    return db.query(models.LearningTask).filter(
        models.LearningTask.credential_id == credential_id
    ).options(joinedload(models.LearningTask.videos)).all()

def update_learning_task_progress(db: Session, task_id: int, current_progress: str = None, is_completed: bool = None, task_url: str = None, study_hours: str = None):
    """ 更新学习任务的进度和状态 """
    db_task = db.query(models.LearningTask).filter(models.LearningTask.id == task_id).first()
    if db_task:
        if current_progress is not None: db_task.current_progress = current_progress
        if is_completed is not None: db_task.is_completed = is_completed
        if task_url is not None: db_task.task_url = task_url
        # 如果 study_hours 为 "0" 或空字符串，则设置为 None
        if study_hours is not None: db_task.study_hours = study_hours if study_hours and study_hours != "0" else None
        db.commit()
        db.refresh(db_task)
    return db_task

def delete_learning_task(db: Session, task_id: int, credential_id: int):
    """ 删除学习任务 """
    db_task = db.query(models.LearningTask).filter(
        models.LearningTask.id == task_id,
        models.LearningTask.credential_id == credential_id
    ).first()
    if db_task:
        db.delete(db_task)
        db.commit()
        return True
    return False

def get_or_create_learning_task(
    db: Session, credential_id: int, task_name: str, task_url: str, study_hours: Optional[str] = None
):
    """ 获取或创建学习任务 """
    db_task = (
        db.query(models.LearningTask)
        .filter_by(credential_id=credential_id, task_name=task_name)
        .first()
    )
    if not db_task:
        # 如果不存在，则创建新任务
        db_task = models.LearningTask(
            credential_id=credential_id,
            task_name=task_name,
            task_url=task_url,
            study_hours=study_hours, # 保存学时
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
    return db_task

# --- 学习视频 (LearningVideo) CRUD 操作 ---
def get_learning_video(db: Session, video_id: int, task_id: int):
    """ 根据视频ID和任务ID获取学习视频 """
    return db.query(models.LearningVideo).filter(
        models.LearningVideo.id == video_id,
        models.LearningVideo.task_id == task_id
    ).first()

def get_learning_videos_by_task_id(db: Session, task_id: int):
    """ 根据任务ID获取所有学习视频 """
    return db.query(models.LearningVideo).filter(
        models.LearningVideo.task_id == task_id
    ).all()

def get_learning_video_by_title_and_task(db: Session, task_id: int, video_title: str):
    """ 根据任务ID和视频标题获取学习视频 """
    return db.query(models.LearningVideo).filter(
        models.LearningVideo.task_id == task_id,
        models.LearningVideo.video_title == video_title
    ).first()

def create_learning_video(db: Session, video: schemas.LearningVideoCreate):
    """ 创建新的学习视频 """
    db_video = models.LearningVideo(
        **video.model_dump(exclude_unset=True) # 使用 exclude_unset=True 避免设置未提供的字段
    )
    # 如果进度或时长为0，将其设为None
    if db_video.current_progress_seconds == 0: db_video.current_progress_seconds = None
    if db_video.total_duration_seconds == 0: db_video.total_duration_seconds = None

    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video

def update_learning_video_progress(db: Session, video_id: int, current_progress_seconds: int = None, total_duration_seconds: int = None, is_completed: bool = None):
    """ 更新学习视频的进度和状态 """
    db_video = db.query(models.LearningVideo).filter(models.LearningVideo.id == video_id).first()
    if db_video:
        if current_progress_seconds is not None: 
            db_video.current_progress_seconds = current_progress_seconds if current_progress_seconds != 0 else None
        if total_duration_seconds is not None: 
            db_video.total_duration_seconds = total_duration_seconds if total_duration_seconds != 0 else None
        if is_completed is not None: db_video.is_completed = is_completed
        db.commit()
        db.refresh(db_video)
    return db_video

def delete_learning_video(db: Session, video_id: int, task_id: int):
    """ 删除学习视频 """
    db_video = db.query(models.LearningVideo).filter(
        models.LearningVideo.id == video_id,
        models.LearningVideo.task_id == task_id
    ).first()
    if db_video:
        db.delete(db_video)
        db.commit()
        return True
    return False

def get_or_create_learning_video(db: Session, task_id: int, video_title: str) -> models.LearningVideo:
    """ 获取或创建学习视频 """
    db_video = get_learning_video_by_title_and_task(db, task_id, video_title)
    if not db_video:
        video_data = schemas.LearningVideoCreate(task_id=task_id, video_title=video_title)
        db_video = create_learning_video(db, video_data)
    elif db_video.video_title != video_title: # 如果视频已存在但标题不同，则更新标题
        db_video.video_title = video_title
        db.commit()
        db.refresh(db_video)
    return db_video