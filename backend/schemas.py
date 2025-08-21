from __future__ import annotations # 用于处理类型提示中的前向引用
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime # 导入 datetime

# --- 学习网站凭据相关 Schema ---
class LearningWebsiteCredentialBase(BaseModel):
    website_url: str  # 学习网站的登录页URL
    website_name: Optional[str] = None # 网站名称
    learning_username: Optional[str] = None # 学习网站用户名
    phone_number: Optional[str] = None
    learning_password: Optional[str] = None # 学习网站密码

class LearningWebsiteCredentialCreate(LearningWebsiteCredentialBase):
    pass

class LearningWebsiteCredential(LearningWebsiteCredentialBase):
    id: int
    system_user_id: int # 关联的系统用户ID
    created_at: datetime
    updated_at: datetime
    tasks: List["LearningTask"] = [] # 新增：关联学习任务列表

    class Config:
        from_attributes = True

# --- 学习任务相关 Schema ---
class LearningTaskBase(BaseModel):
    task_name: str # 任务名称，如“新质生产力的培育与现代化产业体系建设”
    task_url: Optional[str] = None # 进入该任务后的视频列表URL
    current_progress: Optional[str] = "0%" # 任务整体学习进度，例如“0%”, “50%”, “100%”
    is_completed: bool = False
    last_watched_video_index: int = 0
    study_hours: Optional[str] = None # 新增学时字段

    class Config:
        from_attributes = True

class LearningTaskCreate(LearningTaskBase):
    credential_id: int # 创建时需要关联的凭据ID

class LearningTask(LearningTaskBase):
    id: int
    credential_id: int
    created_at: datetime
    updated_at: datetime
    videos: List["LearningVideo"] = [] # 新增：关联学习视频列表

    class Config:
        from_attributes = True

# 新增：用于任务详情显示，包含视频列表
class LearningTaskDetail(LearningTask):
    videos: List[LearningVideo] = [] # 确保这里是 LearningVideo 实例的列表

# --- 学习视频相关 Schema ---
class LearningVideoBase(BaseModel):
    video_title: str # 视频标题

class LearningVideoCreate(LearningVideoBase):
    task_id: int # 创建时需要关联的任务ID
    current_progress_seconds: Optional[int] = None # 视频当前播放秒数
    total_duration_seconds: Optional[int] = None # 视频总时长秒数
    is_completed: Optional[bool] = False

class LearningVideo(LearningVideoBase):
    id: int
    task_id: int
    created_at: datetime
    updated_at: datetime
    current_progress_seconds: Optional[int] # 视频当前播放秒数
    total_duration_seconds: Optional[int] # 视频总时长秒数
    is_completed: bool

    class Config:
        from_attributes = True


# --- 系统用户相关 Schema ---
class SystemUserBase(BaseModel):
    username: str # 用户名（必填）
    phone_number: str # 手机号码（必填）

class SystemUserCreate(SystemUserBase):
    password: str
    password_confirm: str = Field(..., alias="passwordConfirm") # 用于密码确认
    is_active: Optional[bool] = True # 默认用户活跃
    is_approved: Optional[bool] = False # 默认用户未审批

class SystemUserLogin(BaseModel):
    username_or_phone: str = Field(..., alias="usernameOrPhone") # 用户名或手机号码
    password: str

class SystemUserOut(SystemUserBase):
    id: int
    is_active: bool # 用户是否活跃
    is_approved: bool # 用户是否已被管理员审批

    class Config:
        from_attributes = True

# 新增：用于管理员审批用户
class SystemUserApprove(BaseModel):
    user_id: int
    is_approved: bool

# --- 认证相关 Schema ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    learning_username: Optional[str] = None # 统一为 learning_username
    phone_number: Optional[str] = None

# 新增：用于查看学习网站密码时，验证系统用户凭据
class SystemUserCredentials(BaseModel):
    password: str

# --- 自动化相关 Schema ---
class StartWatchingRequest(BaseModel):
    url: str # 自动化学习时提供网站 URL