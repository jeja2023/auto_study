from fastapi import Request, Depends
from typing import Optional
from backend.auth import get_current_system_user
from backend.models import SystemUser

class RequestContext:
    def __init__(self, user_id: Optional[int] = None, username: Optional[str] = None, ip_address: Optional[str] = None):
        self.user_id = user_id
        self.username = username
        self.ip_address = ip_address

async def get_request_context(
    request: Request,
    current_user: Optional[SystemUser] = Depends(get_current_system_user)
) -> RequestContext:
    user_id = current_user.id if current_user else None
    username = current_user.username if current_user else None
    # 尝试从 X-Forwarded-For 获取真实 IP，否则使用直接连接的 IP
    ip_address = request.headers.get("X-Forwarded-For") or (request.client.host if request.client else None)
    return RequestContext(user_id=user_id, username=username, ip_address=ip_address)