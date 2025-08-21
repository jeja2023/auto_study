import os

class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-and-very-long-jwt-secret-key") # JWT 密钥，请在生产环境中更改
    ALGORITHM: str = "HS256" # JWT 算法
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 # Access Token 有效期（分钟）

settings = Settings()