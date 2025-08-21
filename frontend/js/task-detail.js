// 获取页面元素
const taskNameHeader = document.getElementById('taskName');
const taskProgressSpan = document.getElementById('taskProgress');
const taskHoursSpan = document.getElementById('taskHours');
const videosListBody = document.getElementById('videosListBody');

let authToken = null; // 用于存储 JWT Token

// 辅助函数：从 URL 获取查询参数
function getQueryParam(param) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(param);
}

// 辅助函数：将秒数转换为 MM分SS秒 格式
function formatSecondsToMinutesAndSeconds(seconds) {
    if (typeof seconds !== 'number' || isNaN(seconds) || seconds <= 0 || seconds === null) {
        return ""; // 如果为0或null，则不显示
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}分${remainingSeconds}秒`;
}

// 辅助函数：发送带有认证 Token 的请求 (与 index.js 类似，可考虑复用或通用化)
async function authenticatedFetch(url, options) {
    if (!authToken) {
        // 这里可以添加重定向到登录页面的逻辑，或者显示错误消息
        alert('错误：未登录系统用户。请先登录。');
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
        alert('会话已过期，请重新登录。');
        localStorage.removeItem('authToken'); // 移除过期 Token
        window.location.href = '/login'; // 重定向到登录界面
        throw new Error("会话过期");
    }
    return response;
}

// 获取并显示任务详情和视频列表
async function fetchAndDisplayTaskDetails(credentialId) {
    try {
        // 获取凭据名称
        const credentialResponse = await authenticatedFetch(`/api/credentials/${credentialId}`, { method: 'GET' });
        if (!credentialResponse.ok) {
            const errorData = await credentialResponse.json();
            alert(`获取网站凭据详情失败: ${errorData.detail || credentialResponse.statusText}`);
            window.location.href = '/index';
            return;
        }
        const credentialData = await credentialResponse.json();
        const websiteName = credentialData.website_name || `ID ${credentialId} 的网站`;

        const response = await authenticatedFetch(`/api/tasks/credentials/${credentialId}/tasks`, { method: 'GET' });
        if (response.ok) {
            const tasks = await response.json();
            videosListBody.innerHTML = ''; // 清空现有列表

            if (tasks.length === 0) {
                videosListBody.innerHTML = '<tr><td colspan="5" style="text-align: center;">该凭据下暂无学习任务。</td></tr>';
                taskNameHeader.textContent = `${websiteName} 的所有任务详情`;
                taskProgressSpan.textContent = 'N/A';
                taskHoursSpan.textContent = 'N/A';
                return;
            }
            
            // 遍历每个任务并显示其详情和视频
            tasks.forEach(task => {
                // 显示任务的总体信息 (这里简化处理，只显示第一个任务的信息作为代表)
                // 实际上可以遍历所有任务，并为每个任务创建独立的展示区
                // 为了与当前HTML结构匹配，我们假设这里主要关注一个凭据下的所有任务列表，
                // 所以修改标题和总结信息以反映这个凭据下的任务集合。
                const taskSummaryRow = videosListBody.insertRow();
                taskSummaryRow.innerHTML = `
                    <td colspan="5" class="collapsible-task-header" data-task-id="${task.id}" style="font-weight: bold; background-color: #f2f2f2; padding: 10px; cursor: pointer;">
                        <span class="toggle-icon">[-]</span> 任务${task.id}: ${task.task_name} - 进度: ${task.current_progress} ${task.study_hours && task.study_hours !== '0小时' ? `- 学时: ${task.study_hours}` : ''} - 上次观看视频索引: ${task.last_watched_video_index || 0}
                    </td>
                `;

                if (task.videos && task.videos.length > 0) {
                    // 对视频按ID进行排序
                    task.videos.sort((a, b) => a.id - b.id);
                    
                    task.videos.forEach((video, index) => {
                        const row = videosListBody.insertRow();
                        row.classList.add('task-video-item', `task-${task.id}-videos`); // 添加类用于控制显示/隐藏
                        row.innerHTML = `
                            <td>${index + 1}</td>
                            <td>${video.video_title}</td>
                            <td>${formatSecondsToMinutesAndSeconds(video.current_progress_seconds)}</td>
                            <td>${formatSecondsToMinutesAndSeconds(video.total_duration_seconds)}</td>
                            <td>${video.is_completed ? '是' : '否'}</td>
                        `;
                    });
                } else {
                    const row = videosListBody.insertRow();
                    row.classList.add('task-video-item', `task-${task.id}-videos`); // 确保无视频行也被隐藏/显示
                    row.innerHTML = `<td colspan="5" style="text-align: center;">该任务暂无视频。</td>`; /* colspan 调整为5 */
                }
            });

            // 更新顶部的任务摘要信息，可以根据所有任务的总进度来计算
            const totalTasksCount = tasks.length;
            const completedTasksCount = tasks.filter(t => t.is_completed).length;
            const overallProgress = totalTasksCount > 0 ? (completedTasksCount / totalTasksCount * 100).toFixed(2) : '0.00';

            taskNameHeader.textContent = `${websiteName}的任务详情`;
            taskProgressSpan.textContent = `${completedTasksCount} / ${totalTasksCount} (${overallProgress}%)`;
            taskHoursSpan.textContent = tasks.reduce((sum, t) => sum + (parseInt(t.study_hours) || 0), 0) + '小时';

        } else {
            const errorData = await response.json();
            alert(`获取任务详情失败: ${errorData.detail || response.statusText}`);
        }
    } catch (error) {
        console.error('获取任务详情失败:', error);
        alert('获取任务详情失败，请检查网络或后端服务。' + error.message);
    }
}

// 页面加载时执行
document.addEventListener('DOMContentLoaded', () => {
    authToken = localStorage.getItem('authToken');
    if (!authToken) {
        window.location.href = '/login'; // 未登录则重定向到登录界面
        return;
    }

    const credentialId = getQueryParam('credentialId');
    if (credentialId) {
        fetchAndDisplayTaskDetails(credentialId);
    } else {
        alert('错误：未提供凭据 ID。');
        window.location.href = '/index'; // 如果没有 credentialId，返回主页
    }

    // 为任务标题添加点击事件，实现收起/展开功能
    videosListBody.addEventListener('click', (event) => {
        const target = event.target.closest('.collapsible-task-header');
        if (target) {
            const taskId = target.dataset.taskId;
            const videoRows = document.querySelectorAll(`.task-${taskId}-videos`);
            const toggleIcon = target.querySelector('.toggle-icon');

            videoRows.forEach(row => {
                if (row.style.display === 'none') {
                    row.style.display = 'table-row'; // 展开
                    if (toggleIcon) toggleIcon.textContent = '[-]';
                } else {
                    row.style.display = 'none'; // 收起
                    if (toggleIcon) toggleIcon.textContent = '[+]';
                }
            });
        }
    });
});