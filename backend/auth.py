from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.config import settings
from backend.schemas import TokenData
from backend.database import get_db
from backend import crud, models

# OAuth2PasswordBearer 是一种安全方案的实现，它将 token 作为 bearer token 发送
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/users/token") # tokenUrl 是用户获取 token 的端点

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """ 创建 JWT Access Token """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str, credentials_exception):
    """ 验证 JWT Access Token 的有效性 """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        phone_number: Optional[str] = payload.get("phone_number")
        if username is None and phone_number is None:
            raise credentials_exception
        token_data = TokenData(learning_username=username, phone_number=phone_number) # 统一为 learning_username
    except JWTError:
        raise credentials_exception
    return token_data

async def get_current_system_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """ 获取当前认证的系统用户 """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = verify_access_token(token, credentials_exception)
    
    # 尝试根据用户名或手机号找到用户
    user = None
    if token_data.learning_username: # 统一为 learning_username
        user = crud.get_system_user_by_username(db, username=token_data.learning_username) # 统一为 learning_username
    elif token_data.phone_number:
        user = crud.get_system_user_by_phone_number(db, phone_number=token_data.phone_number)
    
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin_user(current_user: models.SystemUser = Depends(get_current_system_user)):
    """ 获取当前认证的管理员用户 """
    if current_user.username != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员用户才能执行此操作",
        )
    return current_user