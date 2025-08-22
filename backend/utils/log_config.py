import logging
from logging.handlers import RotatingFileHandler
import os

from backend.database import SessionLocal # 导入数据库会话
from backend import models # 导入模型
from collections import deque # 导入 deque

# 定义日志文件路径
LOG_DIR = "./logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# 确保日志目录存在
os.makedirs(LOG_DIR, exist_ok=True)

# 用于存储最近的日志条目，供WebSocket实时推送
_websocket_log_queue = deque(maxlen=1000) # 最多保留1000条日志

# 新增：定义要忽略的日志消息子字符串
IGNORED_MESSAGES_SUBSTRINGS = [
    "系统日志 WebSocket", # 匹配连接和断开连接
    "日志广播任务已启动",
    "WebSocket连接已清理",
    "Application startup: Initializing database",
    "管理员用户 'admin' 已存在。"
]

class DbLogHandler(logging.Handler):
    """ 自定义日志处理器，将日志写入数据库 """
    def emit(self, record):
        # 避免在数据库连接还未建立时或处理数据库相关日志时发生循环引用
        if record.name.startswith('sqlalchemy') or record.name.startswith('backend.database'):
            return

        formatted_message = self.format(record) # 格式化消息

        # 【调试用】打印原始消息和格式化后的消息
        # print(f"[DbLogHandler Debug] Raw Record Message: {record.message}")
        # print(f"[DbLogHandler Debug] Formatted Message: {formatted_message}")
        # print(f"[DbLogHandler Debug] Record Name: {record.name}")
        # print(f"[DbLogHandler Debug] Record Level: {record.levelname}")

        # 新增过滤逻辑：如果消息包含任何一个忽略的子字符串，则跳过
        for substring in IGNORED_MESSAGES_SUBSTRINGS:
            if substring in formatted_message:
                # print(f"[DbLogHandler Debug] Filtered: {formatted_message}") # 调试用
                return

        # 从 record 中获取 extra 属性
        user_id = getattr(record, 'user_id', None)
        ip_address = getattr(record, 'ip_address', None)
        username = getattr(record, 'username', None)

        db = SessionLocal()
        try:
            log_entry = models.LogEntry(
                level=record.levelname,
                message=formatted_message, # 使用格式化后的消息
                user_id=user_id, # 设置 user_id
                ip_address=ip_address, # 设置 ip_address
            )
            db.add(log_entry)
            db.commit()
            
            # 同时将日志添加到队列，供WebSocket推送，发送结构化数据
            log_data = {
                "timestamp": record.asctime.split(',')[0], # 移除毫秒
                "level": record.levelname,
                "message": formatted_message, # 使用格式化后的消息
                "user_id": user_id,
                "username": username,
                "ip_address": ip_address
            }
            _websocket_log_queue.append(log_data)

        except Exception as e:
            # 如果数据库写入失败，打印错误到控制台，但不阻止其他日志处理器工作
            print(f"Error writing log to database: {e}")
        finally:
            db.close()

def setup_logging():
    # 获取根日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # 设置全局最低日志级别

    # 避免重复添加处理器
    if not logger.handlers:
        # 创建一个格式器，定义日志输出格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # 创建一个文件处理器，用于将日志写入文件
        # RotatingFileHandler 会在文件达到一定大小时自动轮换，并保留备份
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        ) # 10MB，保留5个备份
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO) # 文件日志级别
        logger.addHandler(file_handler)

        # 创建一个控制台处理器，用于将日志输出到控制台
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO) # 控制台日志级别
        logger.addHandler(console_handler)

        # 创建一个数据库处理器
        db_handler = DbLogHandler()
        db_handler.setLevel(logging.INFO) # 数据库日志级别
        db_handler.setFormatter(formatter) # 使用相同的格式器
        logger.addHandler(db_handler)

    # 对于DrissionPage等库的日志，可以单独设置级别，避免过度输出
    logging.getLogger('DrissionPage').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('uvicorn').setLevel(logging.ERROR)
    logging.getLogger('uvicorn.access').setLevel(logging.ERROR)
    logging.getLogger('mysql.connector').setLevel(logging.WARNING) # 添加这行来控制mysql.connector的日志

# 在应用程序启动时调用此函数以配置日志