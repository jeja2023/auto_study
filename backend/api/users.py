from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend import crud, schemas
from backend.database import get_db
from backend.auth import create_access_token, get_current_admin_user, get_current_system_user # 导入 get_current_system_user
from backend.config import settings
from typing import List # 导入List

router = APIRouter()

@router.post("/register", response_model=schemas.SystemUserOut)
async def register_system_user(user: schemas.SystemUserCreate, db: Session = Depends(get_db)):
    """ 注册一个新的系统用户。 """
    if user.password != user.password_confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="两次输入的密码不一致！")
    
    # 检查用户名或手机号码是否已存在
    db_user_by_username = None
    db_user_by_phone = None

    if user.username:
        db_user_by_username = crud.get_system_user_by_username(db, username=user.username)
    if user.phone_number:
        db_user_by_phone = crud.get_system_user_by_phone_number(db, phone_number=user.phone_number)

    if db_user_by_username or db_user_by_phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名或手机号码已被注册！")
    
    new_user = crud.create_system_user(db=db, user=user)
    return new_user

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """ 系统用户登录并获取 Access Token。 """
    user = crud.get_system_user_by_username_or_phone(db, username_or_phone=form_data.username) # form_data.username 实际是用户名或手机号
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名/手机号码或密码不正确",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户未被管理员审批，请联系管理员。",
        )
    
    # 根据用户登录时提供的是用户名还是手机号，将相应的数据放入 JWT payload
    token_data = {}
    if user.username:
        token_data["sub"] = user.username
    if user.phone_number:
        token_data["phone_number"] = user.phone_number

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data=token_data, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.SystemUserOut)
async def get_current_user_info(current_user: schemas.SystemUserOut = Depends(get_current_system_user)):
    """ 获取当前登录的用户信息 """
    return current_user

@router.get("/unapproved-users", response_model=List[schemas.SystemUserOut])
async def get_unapproved_users(db: Session = Depends(get_db), admin_user: schemas.SystemUserOut = Depends(get_current_admin_user)):
    """ 获取所有未审批的用户列表 (仅管理员可访问) """
    unapproved_users = crud.get_unapproved_system_users(db)
    return unapproved_users

@router.post("/approve-user", response_model=schemas.SystemUserOut)
async def approve_user(user_approve: schemas.SystemUserApprove, db: Session = Depends(get_db), admin_user: schemas.SystemUserOut = Depends(get_current_admin_user)):
    """ 审批指定用户 (仅管理员可访问) """
    db_user = crud.approve_system_user(db, user_id=user_approve.user_id)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return db_user