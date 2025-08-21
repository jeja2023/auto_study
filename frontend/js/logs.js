// frontend/static/js/logs.js

document.addEventListener('DOMContentLoaded', () => {
    const logTableBody = document.getElementById('logTableBody');
    const logTableContainer = logTableBody.closest('.log-table-container'); // 获取表格的滚动容器
    const authToken = localStorage.getItem('authToken'); // 从localStorage获取authToken

    if (!authToken) {
        // logOutput.textContent = '错误: 未找到认证令牌，请先登录。'; // 旧的文本输出，已弃用
        const row = logTableBody.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 6; // 跨越所有列
        cell.textContent = '错误: 未找到认证令牌，请先登录。';
        cell.style.color = 'red';
        console.error('未找到认证令牌');
        return;
    }

    // 构建WebSocket URL
    // 假设后端运行在与前端相同的域名和端口上
    // 并且 WebSocket 路径是 /api/tasks/ws/logs
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/tasks/ws/logs?token=${authToken}`;

    const socket = new WebSocket(wsUrl);

    // 辅助函数：将日志数据添加到表格
    function addLogToTable(logData) {
        const row = logTableBody.insertRow();

        // 时间戳
        const timeCell = row.insertCell();
        timeCell.textContent = logData.timestamp;

        // 级别
        const levelCell = row.insertCell();
        levelCell.textContent = logData.level;
        levelCell.classList.add(`log-level-${logData.level}`); // 添加级别类以应用颜色

        // 消息
        const messageCell = row.insertCell();
        messageCell.textContent = logData.message;

        // 用户ID
        const userIdCell = row.insertCell();
        userIdCell.textContent = logData.user_id !== null ? logData.user_id : '';

        // 用户名
        const usernameCell = row.insertCell();
        usernameCell.textContent = logData.username !== null ? logData.username : '';

        // IP地址
        const ipAddressCell = row.insertCell();
        ipAddressCell.textContent = logData.ip_address !== null ? logData.ip_address : '';

        // 自动滚动到底部
        if (logTableContainer) {
            logTableContainer.scrollTop = logTableContainer.scrollHeight;
        }
    }

    socket.onopen = (event) => {
        // console.log('WebSocket连接已建立，开始接收日志...');
        console.log('WebSocket连接已建立', event);
    };

    socket.onmessage = (event) => {
        try {
            const logData = JSON.parse(event.data); // 解析JSON数据
            addLogToTable(logData);
        } catch (e) {
            console.error('解析日志数据失败:', e, event.data);
            // 如果解析失败，仍然显示原始消息，但只显示在控制台
            // const row = logTableBody.insertRow();
            // const cell = row.insertCell();
            // cell.colSpan = 5;
            // cell.textContent = `[解析错误] ${event.data}`;
            // cell.style.color = 'orange';
        }
    };

    socket.onclose = (event) => {
        const row = logTableBody.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 6; // 跨越所有列
        cell.textContent = `WebSocket连接已关闭。Code: ${event.code}, Reason: ${event.reason}`;
        cell.style.color = 'orange';
        console.warn('WebSocket连接已关闭', event);
        if (event.code === 1008) { // 1008: 策略违反 (通常是认证失败)
            const authErrorRow = logTableBody.insertRow();
            const authErrorCell = authErrorRow.insertCell();
            authErrorCell.colSpan = 5;
            authErrorCell.textContent = '认证失败，请重新登录。';
            authErrorCell.style.color = 'red';
            alert('认证失败，请重新登录！');
            window.location.href = '/login'; // 重定向到登录页面
        }
    };

    socket.onerror = (error) => {
        const row = logTableBody.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 6; // 跨越所有列
        cell.textContent = 'WebSocket发生错误！请检查网络连接或后端服务。'
        cell.style.color = 'red';
        console.error('WebSocket发生错误', error);
    };

    // Optional: Keep connection alive by sending pings if server supports it
    // setInterval(() => {
    //     if (socket.readyState === WebSocket.OPEN) {
    //         socket.send('ping');
    //     }
    // }, 30000);
});