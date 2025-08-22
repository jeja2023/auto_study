// 获取页面元素
const credentialsListBody = document.getElementById('credentialsListBody');
const addNewCredentialBtn = document.getElementById('addNewCredentialBtn');
// const statusMessageDiv = document.getElementById('statusMessage'); // 已移除

// 获取导航栏元素
const adminLink = document.getElementById('adminLink');
const logoutButton = document.getElementById('logoutButton');

// 密码查看模态对话框相关元素
const passwordModal = document.getElementById('passwordModal');
const closeButton = document.querySelector('.close-button');
const systemPasswordInput = document.getElementById('systemPassword');
const confirmViewPasswordBtn = document.getElementById('confirmViewPasswordBtn');
const cancelViewPasswordBtn = document.getElementById('cancelViewPasswordBtn');
// const passwordDisplayDiv = document.getElementById('passwordDisplay'); // 已移除
// const modalStatusMessageDiv = document.getElementById('modalStatusMessage'); // 已移除

let authToken = null; // 用于存储 JWT Token
let currentViewingCredentialId = null; // 存储当前正在查看密码的凭据ID

// 辅助函数：发送带有认证 Token 的请求
async function authenticatedFetch(url, options) {
    if (!authToken) {
        alert('错误：未登录系统用户。请先登录。');
        window.location.href = '/login'; // 未登录则重定向到登录界面
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

// 获取并显示凭据列表
async function fetchAndDisplayCredentials() {
    try {
        const response = await authenticatedFetch('/api/credentials/all', { method: 'GET' });
        if (response.ok) {
            const credentials = await response.json();
            credentialsListBody.innerHTML = ''; // 清空现有列表

            const emptyListMessageRow = document.getElementById('emptyListMessageRow');
            if (credentials.length === 0) {
                if (emptyListMessageRow) {
                    emptyListMessageRow.style.display = ''; // 显示空列表消息
                }
                // alert('未找到任何凭据。'); // 移除此行，因为页面上已经有提示
                return;
            } else {
                if (emptyListMessageRow) {
                    emptyListMessageRow.style.display = 'none'; // 隐藏空列表消息
                }
            }
            credentials.forEach(credential => {
                const row = credentialsListBody.insertRow();
                const videoListUrl = credential.video_list_url || '未设置';
                const displayVideoListUrl = videoListUrl.length > 50 ? videoListUrl.substring(0, 47) + '...' : videoListUrl;
                // 密码列显示“查看密码”按钮
                const passwordCellContent = credential.learning_password ? 
                    `<button class="btn-view-password small-action-btn" data-id="${credential.id}">查看密码</button>` :
                    `未设置`;

                // 计算任务进度
                let totalTasks = 0;
                let completedTasks = 0;
                let taskProgressContent = '无任务';

                if (credential.tasks && credential.tasks.length > 0) {
                    totalTasks = credential.tasks.length;
                    completedTasks = credential.tasks.filter(task => task.is_completed).length;
                    
                    // 计算总学时
                    let totalStudyHours = 0;
                    credential.tasks.forEach(task => {
                        if (task.study_hours) {
                            // 假设 study_hours 是 "X小时" 或 "X"
                            const hours = parseInt(task.study_hours.replace('小时', ''));
                            if (!isNaN(hours)) {
                                totalStudyHours += hours;
                            }
                        }
                    });

                    // 调整显示顺序：学时在前，进度在后
                    taskProgressContent = `学时: ${totalStudyHours}小时 - 进度: ${completedTasks} / ${totalTasks} (${(completedTasks / totalTasks * 100).toFixed(2)}%)`;
                    
                    // 可以考虑添加一个 tooltip 或展开/折叠功能来显示详细任务列表
                    const detailedTasks = credential.tasks.map(task => 
                        `<li>${task.task_name} - ${task.current_progress} (${task.study_hours || '0小时'})</li>` // 详细任务也显示学时
                    ).join('');
                    taskProgressContent = `
                        <div title="${credential.website_name || 'N/A'}">
                            <span class="task-summary">${taskProgressContent}</span>
                            <div class="task-details" style="display:none;">
                                <ul>${detailedTasks}</ul>
                            </div>
                        </div>
                    `;
                }
                
                row.innerHTML = `
                    <td>${credential.id}</td>
                    <td>${credential.website_name || '未设置'}</td>
                    <td>${credential.website_url}</td>
                    <td>${credential.learning_username || '未设置'}</td>
                    <td>${passwordCellContent}</td>
                    <td>
                        <div class="action-buttons">
                            <label class="checkbox-container"><input type="checkbox" class="headless-checkbox" data-id="${credential.id}"> 无头模式</label>
                            <button class="btn-edit main-action-button" data-id="${credential.id}">编辑</button>
                            <button class="btn-delete main-action-button" data-id="${credential.id}">删除</button>
                            <button class="btn-start main-action-button" data-id="${credential.id}">开始学习</button>
                            <button class="btn-view-tasks main-action-button" data-id="${credential.id}">查看任务</button>
                        </div>
                    </td>
                `;
            });
        } else {
            const errorData = await response.json();
            alert(`获取凭据列表失败: ${errorData.detail || response.statusText}`);
        }
    } catch (error) {
        console.error('获取凭据列表失败:', error);
        alert('获取凭据列表失败，请检查网络或后端服务。' + error.message);
    }
}

// 处理删除凭据
async function deleteCredential(id) {
    if (!confirm('确定要删除此凭据吗？')) {
        return;
    }
    alert('正在删除凭据...');
    try {
        const response = await authenticatedFetch(`/api/credentials/${id}`, { method: 'DELETE' });
        if (response.ok) {
            alert('凭据删除成功！');
            fetchAndDisplayCredentials(); // 刷新列表
        } else {
            const errorData = await response.json();
            alert(`删除凭据失败: ${errorData.detail || response.statusText}`);
        }
    } catch (error) {
        console.error('删除凭据失败:', error);
        alert('删除凭据失败，请检查网络或后端服务。' + error.message);
    }
}

// 处理通过 ID 启动学习任务
async function startLearningById(id, isHeadless) {
    // 1. 立即在新标签页打开实时日志页面
    window.open(`/auto-learn?credentialId=${id}`, '_blank'); // 传递凭据ID并在新标签页打开

    try {
        const response = await authenticatedFetch(`/api/credentials/launch-web-for-login/${id}`, {
            method: 'POST',
            body: JSON.stringify({ headless: isHeadless }) // 将headless状态传递给后端
        });

        const data = await response.json();
        // alert(data.message); // 移除启动成功提示
        // 理论上这里不需要再次跳转，因为页面已经打开了
        // if (response.ok) {
        //     window.open(`/auto-learn?credentialId=${id}`, '_blank'); 
        // }
    } catch (error) {
        console.error('启动学习任务失败:', error);
        alert('启动学习任务失败: ' + error.message);
    }
}

// 检查当前用户是否为管理员
async function checkAdminStatus() {
    try {
        const response = await authenticatedFetch('/api/users/me', { method: 'GET' });
        const user = await response.json();

        if (user.username === 'admin') {
            adminLink.style.display = 'block'; // 显示管理员面板链接
        } else {
            adminLink.style.display = 'none'; // 隐藏管理员面板链接
        }
    } catch (error) {
        console.error('检查管理员状态失败:', error);
        adminLink.style.display = 'none'; // 默认隐藏
    }
}

// 退出登录函数
function logout() {
    localStorage.removeItem('authToken'); // 移除本地存储的 Token
    window.location.href = '/login'; // 重定向到登录页面
}

// 页面加载时执行
document.addEventListener('DOMContentLoaded', () => {
    authToken = localStorage.getItem('authToken');
    if (!authToken) {
        window.location.href = '/login';
        return;
    }
    fetchAndDisplayCredentials();
    checkAdminStatus(); // 检查管理员状态

    // 监听“添加新凭据”按钮点击事件
    addNewCredentialBtn.addEventListener('click', () => {
        window.location.href = '/credentials-setup'; // 跳转到添加/编辑页面
    });

    // 监听表格中的动态生成按钮（编辑、删除、开始学习，以及新增的查看密码）
    credentialsListBody.addEventListener('click', async (event) => { // 将事件监听器改为 async
        const target = event.target;
        const credentialId = target.dataset.id;

        // 使用 .closest() 方法来确保获取到按钮元素本身
        const editButton = target.closest('.btn-edit');
        const deleteButton = target.closest('.btn-delete');
        const startButton = target.closest('.btn-start');
        const viewPasswordButton = target.closest('.btn-view-password');
        const viewTasksButton = target.closest('.btn-view-tasks'); // 新增：查看任务按钮

        if (editButton) {
            // 跳转到编辑页面，并传递凭据ID
            window.open(`/credentials-setup?id=${editButton.dataset.id}`, '_blank');
        } else if (deleteButton) {
            deleteCredential(deleteButton.dataset.id);
        } else if (startButton) {
            const row = startButton.closest('tr'); // 获取父行
            const headlessCheckbox = row.querySelector(`.headless-checkbox[data-id="${credentialId}"]`); // 查找同行的复选框
            const isHeadless = headlessCheckbox ? headlessCheckbox.checked : false; // 获取选中状态
            startLearningById(startButton.dataset.id, isHeadless); // 传递 isHeadless
        } else if (viewPasswordButton) { // 处理查看密码按钮点击
            currentViewingCredentialId = viewPasswordButton.dataset.id; // 保存当前要查看的凭据ID
            passwordModal.style.display = 'block'; // 显示模态对话框
            // alert('请输入系统密码以查看学习密码。'); // 移除状态消息
            systemPasswordInput.value = '';
        } else if (viewTasksButton) { // 处理查看任务按钮点击
            window.open(`/task-detail.html?credentialId=${viewTasksButton.dataset.id}`, '_blank');
        }
    });

    // 模态对话框关闭按钮事件
    closeButton.addEventListener('click', () => {
        passwordModal.style.display = 'none';
    });

    // 点击模态对话框外部关闭
    window.addEventListener('click', (event) => {
        if (event.target == passwordModal) {
            passwordModal.style.display = 'none';
        }
    });

    // 模态对话框取消按钮事件
    cancelViewPasswordBtn.addEventListener('click', () => {
        passwordModal.style.display = 'none';
    });

    // 模态对话框确认查看密码按钮事件
    confirmViewPasswordBtn.addEventListener('click', async () => {
        const systemPassword = systemPasswordInput.value;

        if (!systemPassword) {
            alert('请输入系统密码。');
            return;
        }
        
        alert('正在验证，请稍候...');

        try {
            const response = await authenticatedFetch(`/api/credentials/view-learning-password/${currentViewingCredentialId}`, {
                method: 'POST',
                body: JSON.stringify({
                    password: systemPassword
                })
            });
            const data = await response.json();

            if (response.ok) {
                const learningPassword = data.learning_password;
                alert(`学习网站密码: ${learningPassword}`); // 显示密码
                // alert('验证成功！'); // 移除状态消息
                // 密码显示5秒后自动隐藏
                setTimeout(() => {
                    passwordModal.style.display = 'none';
                }, 5000);
            } else {
                alert(data.detail || '验证失败，请重试。');
            }
        } catch (error) {
            console.error('查看密码请求失败:', error);
            alert('请求失败，请检查网络或后端服务。 ' + error.message);
        }
    });

    // 监听“退出登录”按钮点击事件
    logoutButton.addEventListener('click', logout);

});