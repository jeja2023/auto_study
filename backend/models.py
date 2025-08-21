from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from backend.database import Base

class SystemUser(Base):
    __tablename__ = "system_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    phone_number = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_approved = Column(Boolean, default=False) # 新增字段：是否已被管理员审批

    credentials = relationship("LearningWebsiteCredential", back_populates="owner", cascade="all, delete-orphan")

class LearningWebsiteCredential(Base):
    __tablename__ = "learning_website_credentials"

    id = Column(Integer, primary_key=True, index=True)
    system_user_id = Column(Integer, ForeignKey("system_users.id"), nullable=False)
    website_name = Column(String(255), nullable=True) # 新增：网站名称
    website_url = Column(String(255), unique=True, index=True, nullable=False) # 网站URL应是唯一的
    learning_username = Column(String(255), nullable=True) # 修改：学习网站用户名
    learning_password = Column(String(255), nullable=True) # 新增：学习网站密码
    # video_list_url = Column(String(255), nullable=True) # 此字段将废弃或改变用途，因为现在有多个任务和视频URL
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    owner = relationship("SystemUser", back_populates="credentials")
    tasks = relationship("LearningTask", back_populates="credential", cascade="all, delete-orphan") # 新增：关联学习任务

# 新增：学习任务模型
class LearningTask(Base):
    __tablename__ = "learning_tasks"

    id = Column(Integer, primary_key=True, index=True)
    credential_id = Column(Integer, ForeignKey("learning_website_credentials.id"), nullable=False)
    task_name = Column(String(255), nullable=False) # 任务名称，如“新质生产力的培育与现代化产业体系建设”
    task_url = Column(String(255), nullable=True) # 进入该任务后的视频列表URL
    current_progress = Column(String(50), default="0.00%") # 任务整体学习进度，例如“0%”, “50%”, “100%”
    is_completed = Column(Boolean, default=False)
    last_watched_video_index = Column(Integer, default=0) # 记录上次学到哪个视频
    study_hours = Column(String(50), nullable=True) # 新增学时字段
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    credential = relationship("LearningWebsiteCredential", back_populates="tasks")
    videos = relationship("LearningVideo", back_populates="task", cascade="all, delete-orphan")

# 新增：学习视频模型
class LearningVideo(Base):
    __tablename__ = "learning_videos"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("learning_tasks.id"), nullable=False)
    video_title = Column(String(512), nullable=False) # 视频标题
    current_progress_seconds = Column(Integer, nullable=True) # 视频当前播放秒数，可空
    total_duration_seconds = Column(Integer, nullable=True) # 视频总时长秒数，可空
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    task = relationship("LearningTask", back_populates="videos")

# 新增：日志条目模型
class LogEntry(Base):
    __tablename__ = "log_entries"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, server_default=func.now())
    level = Column(String(50), nullable=False) # 例如: INFO, WARNING, ERROR
    message = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("system_users.id"), nullable=True) # 关联的系统用户ID，可为空
    ip_address = Column(String(45), nullable=True) # 存储IP地址，IPv6最大长度45字符

    # 添加与 SystemUser 的关系，以便通过日志查找用户
    user = relationship("SystemUser", primaryjoin="LogEntry.user_id == SystemUser.id", foreign_keys=[user_id])