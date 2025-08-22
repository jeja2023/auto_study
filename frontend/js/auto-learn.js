// 获取页面元素
const stopLearningBtn = document.getElementById('stopLearningBtn');
const logDisplay = document.getElementById('logDisplay');
const statusMessageDiv = document.getElementById('statusMessage');

let authToken = null;
let logWebSocket = null;

// 辅助函数：显示状态消息
function showStatusMessage(message, isError = false) {
    statusMessageDiv.textContent = message;
    statusMessageDiv.style.display = 'block';
    statusMessageDiv.style.backgroundColor = isError ? '#f8d7da' : '#d4edda'; // 错误显示红色背景，成功显示绿色背景
    statusMessageDiv.style.color = isError ? '#721c24' : '#155724';
    // 3秒后自动隐藏
    setTimeout(() => {
        statusMessageDiv.style.display = 'none';
    }, 3000);
}

// 辅助函数：发送带有认证 Token 的请求
async function authenticatedFetch(url, options) {
    if (!authToken) {
        showStatusMessage('错误：未登录系统用户。请先登录。', true);
        window.location.href = '/login';
        throw new Error("未认证用户");
    }
    const headers = {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json',
        ...(options.headers || {})
    };
    const newOptions = { ...options, headers };

    const response = await fetch(url, newOptions);

    if (response.status === 401) {
        showStatusMessage('会话已过期，请重新登录。', true);
        localStorage.removeItem('authToken');
        window.location.href = '/login';
        throw new Error("会话过期");
    }
    return response;
}

// 连接日志 WebSocket
function connectLogWebSocket() {
    if (logWebSocket && logWebSocket.readyState === WebSocket.OPEN) {
        return; // 如果已连接，则不重复连接
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    if (!authToken) {
        console.error("无法连接日志 WebSocket: 认证 Token 不存在。");
        showStatusMessage('错误：未登录系统用户。请先登录。', true);
        window.location.href = '/login';
        return;
    }
    logWebSocket = new WebSocket(`${wsProtocol}//${window.location.host}/api/tasks/ws/logs?token=${authToken}`);

    logWebSocket.onopen = (event) => {
        console.log('日志 WebSocket 已连接。');
        logDisplay.textContent = ''; // 清空所有旧日志
        // logDisplay.textContent = `WebSocket 连接成功，等待日志...\n`; // 移除前端的欢迎消息
    };

    logWebSocket.onmessage = (event) => {
        try {
            const logData = JSON.parse(event.data);

            // 定义要忽略的日志消息子字符串 (与后端log_config.py中的IGNORED_MESSAGES_SUBSTRINGS保持一致)
            const IGNORED_MESSAGES_SUBSTRINGS = [
                "系统日志 WebSocket", // 匹配连接和断开连接
                "日志广播任务已启动",
                "WebSocket连接已清理",
                "Application startup: Initializing database",
                "管理员用户 'admin' 已存在。",
                "INFO:     connection open", // Uvicorn连接日志
                "INFO:     connection closed" // Uvicorn连接日志
            ];

            // 过滤日志：如果消息包含任何一个忽略的子字符串，则跳过
            for (const substring of IGNORED_MESSAGES_SUBSTRINGS) {
                if (logData.message.includes(substring)) {
                    return; // 忽略此日志
                }
            }

            let logEntry = logData.message; // Extract the message field
            
            // 移除时间戳、模块名和日志级别前缀 (例如: "2025-08-21 19:33:27,308 - backend.main - INFO - ")
            logEntry = logEntry.replace(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - [a-zA-Z0-9\._]+ - (INFO|WARNING|ERROR|DEBUG|CRITICAL) - /, '');
            
            // 移除 AutoWatcherRunner 特有前缀 (如果仍然存在)
            logEntry = logEntry.replace(/^\s*\[AutoWatcherRunner\](\[用户 \d+\])?\s*/, '').trim();
            
            logDisplay.textContent += logEntry + '\n';
            logDisplay.scrollTop = logDisplay.scrollHeight;
        } catch (e) {
            // 检查是否是Uvicorn的内部连接日志，如果是则忽略
            const rawMessage = event.data.trim();
            if (rawMessage.includes("INFO:     connection open") || rawMessage.includes("INFO:     connection closed")) {
                console.log("忽略Uvicorn连接日志 (auto-learn):", rawMessage);
                return; // 忽略这些日志
            }
            console.error("解析日志消息失败:", e, "原始数据:", event.data);
            logDisplay.textContent += `[解析错误] ${event.data}\n`; // Fallback to raw data on error
        }
    };

    logWebSocket.onerror = (event) => {
        console.error('日志 WebSocket 错误:', event);
        showStatusMessage('WebSocket 连接错误！请检查后端。' + event.message, true);
        // logDisplay.textContent += 'WebSocket 连接错误！请检查后端。\n';
    };

    logWebSocket.onclose = (event) => {
        console.log('日志 WebSocket 已关闭:', event);
        showStatusMessage('WebSocket 连接已关闭。' + event.reason, true);
        // logDisplay.textContent += 'WebSocket 连接已关闭。\n';
    };
}

// 监听“停止学习”按钮点击事件
stopLearningBtn.addEventListener('click', async () => {
    showStatusMessage('正在发送停止学习任务请求...');
    // 隐藏停止按钮，避免重复点击
    stopLearningBtn.style.display = 'none';

    try {
        const response = await authenticatedFetch('/api/tasks/stop-auto-watching', {
            method: 'POST'
        });
        const data = await response.json();
        showStatusMessage(data.message, false);
        // 停止任务后可以重定向到主页，或者在当前页面显示停止信息
        // 这里选择在当前页面显示信息
    } catch (error) {
        console.error('停止学习任务失败:', error);
        showStatusMessage('停止学习任务失败: ' + error.message, true);
        // 如果停止失败，重新显示停止按钮
        stopLearningBtn.style.display = 'inline-block';
    }
});

// 页面加载时执行
document.addEventListener('DOMContentLoaded', () => {
    authToken = localStorage.getItem('authToken');
    if (!authToken) {
        window.location.href = '/login';
        return;
    }
    // 连接日志 WebSocket
    connectLogWebSocket();
});