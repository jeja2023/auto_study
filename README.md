# 自动学习应用

## 项目简介

这是一个基于 FastAPI 和 DrissionPage 的自动学习应用，旨在帮助用户自动化完成在线学习任务。它提供了一个用户友好的 Web 界面，支持用户注册、登录、管理学习网站凭据，并能启动浏览器自动化任务来观看视频和跟踪学习进度。

## 主要功能

- **用户认证**：安全的注册和登录系统。
- **凭据管理**：用户可以存储和管理多个学习网站的登录凭据。
- **学习任务自动化**：
  - 启动无头（或有头）浏览器实例，自动登录学习网站。
  - 扫描课程列表并识别未完成的学习任务。
  - 自动播放任务中的视频，并实时更新学习进度。
  - 支持视频播放监控，确保学习任务完成。
- **实时日志**：通过 WebSocket 提供实时的系统日志，方便用户监控自动化任务的运行状态。
- **IP 地址记录**：在日志中记录用户的登录 IP 地址。

## 近期更新

- **优化实时日志显示**：前端实时日志（包括系统日志页面和自动学习实时日志页面）已优化，过滤掉 WebSocket 连接和服务器内部的冗余日志，使日志输出更加清晰和专注于实际应用事件。
- **改进自动化任务流程**：修复了自动化学习任务在完成一个任务后无法自动切换到下一个任务的问题。现在，任务完成后能正确返回主任务列表页面，实现连续学习。
- **简化“开始学习”操作**：移除了点击“开始学习”按钮时的弹窗提示，现在将直接在新标签页中打开学习任务，提供更流畅的用户体验。

## 技术栈

- **后端**：
  - Python 3.9+
  - FastAPI：高性能 Web 框架
  - SQLAlchemy：ORM 框架，用于数据库操作
  - Pydantic：数据验证和设置管理
  - python-jose：JWT 认证
  - passlib：密码哈希
  - DrissionPage：基于 Selenium/Playwright 的浏览器自动化库
  - Uvicorn：ASGI 服务器
  - MySQL：数据库
- **前端**：
  - HTML5
  - CSS3 (自定义样式)
  - JavaScript (原生 JS，用于交互和 AJAX 请求)

## 项目结构

```
auto_study/
├── backend/                  # 后端服务代码
│   ├── api/                  # API 路由定义
│   ├── auth.py               # 认证相关逻辑
│   ├── config.py             # 应用配置
│   ├── context.py            # 请求上下文管理
│   ├── crud.py               # 数据库 CRUD 操作
│   ├── database.py           # 数据库连接和会话管理
│   ├── main.py               # FastAPI 应用入口
│   └── utils/                # 实用工具函数
│       ├── auto_watcher_runner.py # 自动化任务执行器
│       ├── log_config.py      # 日志配置
├── frontend/                 # 前端静态文件
│   ├── css/                  # 样式表
│   ├── js/                   # JavaScript 脚本
│   └── *.html                # HTML 页面
├── logs/                     # 应用程序日志文件
│   └── app.log
├── tmp_user_data/            # 浏览器自动化临时用户数据
├── .env                      # 环境变量配置文件
└── requirements.txt          # Python 依赖列表
```

## 环境设置与运行

### 1. 克隆项目

```bash
git clone https://github.com/jeja2023/auto_study.git
cd auto_study
```

### 2. 创建并激活虚拟环境

推荐使用虚拟环境来管理项目依赖。

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

创建或编辑项目根目录下的 `.env` 文件，并添加以下内容：

```dotenv
DATABASE_URL="mysql+mysqlconnector://your_username:your_password@localhost:3306/your_database_name"
SECRET_KEY="your-super-secret-and-very-long-jwt-secret-key"
```

- 将 `your_username`、`your_password` 和 `your_database_name` 替换为您的 MySQL 数据库凭据和数据库名称。
- 将 `SECRET_KEY` 替换为一个足够长且随机的字符串，用于 JWT 加密。

### 5. 运行应用程序

```bash
uvicorn backend.main:app --reload
```

运行成功后，您可以通过浏览器访问 `http://127.0.0.1:8000` 来使用应用程序。

## 贡献

如果您想为本项目贡献代码，请先阅读 `CONTRIBUTING.md` (如果存在)。

## 许可证

本项目采用 MIT 许可证。详见 `LICENSE` 文件 (如果存在)。

---