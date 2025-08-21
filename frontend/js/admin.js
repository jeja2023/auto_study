// frontend/js/admin.js

document.addEventListener('DOMContentLoaded', () => {
    const unapprovedUsersList = document.getElementById('unapprovedUsersList');
    let authToken = localStorage.getItem('authToken'); // 修正：使用 authToken

    // 辅助函数：发送带有认证 Token 的请求（从 index.js 复制过来，或者更优的做法是将其提取到单独的 common.js 或 utils.js 中）
    async function authenticatedFetch(url, options) {
        if (!authToken) { // 使用 let 定义的 authToken
            alert('错误：未找到认证令牌，请先登录。');
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

    if (!authToken) { // 使用 let 定义的 authToken
        unapprovedUsersList.innerHTML = '<p>错误: 未找到认证令牌，请先登录。</p>';
        console.error('未找到认证令牌');
        return;
    }

    async function fetchUnapprovedUsers() {
        try {
            const response = await authenticatedFetch('/api/users/unapproved-users', { // 修正：使用 authenticatedFetch
                method: 'GET' // 修正：无需手动添加 headers
            });

            if (!response.ok) {
                if (response.status === 403) {
                    unapprovedUsersList.innerHTML = '<p>权限不足，只有管理员才能访问此页面。</p>';
                } else if (response.status === 401) {
                    alert('认证失败，请重新登录。');
                    window.location.href = '/login';
                } else {
                    const errorData = await response.json();
                    unapprovedUsersList.innerHTML = `<p>加载用户失败: ${errorData.detail || response.statusText}</p>`;
                }
                return;
            }

            const users = await response.json();
            renderUsers(users);
        } catch (error) {
            unapprovedUsersList.innerHTML = `<p>请求失败: ${error.message}</p>`;
            console.error('获取未审批用户失败:', error);
        }
    }

    async function approveUser(userId) {
        try {
            const response = await authenticatedFetch('/api/users/approve-user', { // 修正：使用 authenticatedFetch
                method: 'POST',
                body: JSON.stringify({ user_id: userId, is_approved: true })
            });

            if (!response.ok) {
                const errorData = await response.json();
                alert(`审批失败: ${errorData.detail || response.statusText}`);
                return;
            }

            alert('用户已成功审批！');
            fetchUnapprovedUsers(); // 重新加载列表
        } catch (error) {
            alert(`审批请求失败: ${error.message}`);
            console.error('审批用户失败:', error);
        }
    }

    function renderUsers(users) {
        if (users.length === 0) {
            unapprovedUsersList.innerHTML = '<p>没有待审批的用户。</p>';
            return;
        }

        unapprovedUsersList.innerHTML = '';
        users.forEach(user => {
            const userDiv = document.createElement('div');
            userDiv.classList.add('user-item');
            userDiv.innerHTML = `
                <span>用户名: ${user.username}</span>
                <span>手机: ${user.phone_number}</span>
                <button class="btn-primary" data-user-id="${user.id}">审批</button>
            `;
            unapprovedUsersList.appendChild(userDiv);
        });

        // 为每个审批按钮添加事件监听器
        document.querySelectorAll('#unapprovedUsersList button').forEach(button => {
            button.addEventListener('click', (event) => {
                const userId = event.target.dataset.userId;
                if (confirm(`确定要审批用户 ${userId} 吗？`)) {
                    approveUser(parseInt(userId));
                }
            });
        });
    }

    fetchUnapprovedUsers(); // 页面加载时立即获取用户
});