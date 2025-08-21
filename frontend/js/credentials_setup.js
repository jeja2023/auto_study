// 获取凭据设置界面元素
const websiteUrlInput = document.getElementById('websiteUrl');
const websiteNameInput = document.getElementById('websiteName'); // 新增：获取网站名称输入框
const taskNameInput = document.getElementById('taskName'); // 新增：获取任务名称输入框
const videoListUrlInput = document.getElementById('videoListUrl'); // 新增：获取视频列表URL输入框
const learningUsernameInput = document.getElementById('learningUsername');
const learningPhoneNumberInput = document.getElementById('learningPhoneNumber');
const learningPasswordInput = document.getElementById('learningPassword'); // 新增：获取学习网站密码输入框
// const learningPasswordInput = document.getElementById('learningPassword'); // 移除密码输入框
// const learningPasswordConfirmInput = document.getElementById('learningPasswordConfirm'); // 移除确认密码输入框
const addCredentialButton = document.getElementById('addCredentialButton');
const backToIndexButton = document.getElementById('backToIndexButton');

// const statusDiv = document.getElementById('status'); // 已移除

let authToken = null; // 用于存储 JWT Token

// 页面加载时检查认证状态
document.addEventListener('DOMContentLoaded', () => {
    authToken = localStorage.getItem('authToken');
    if (!authToken) {
        // 如果没有 Token，重定向到登录页面
        window.location.href = '/login';
        return; // 阻止后续代码执行
    }
    // 检查URL中是否有凭据ID，用于编辑模式
    const urlParams = new URLSearchParams(window.location.search);
    const credentialId = urlParams.get('id');
    if (credentialId) {
        fetchCredentialForEdit(credentialId);
        addCredentialButton.textContent = '更新凭据'; // 修改按钮文本
    }
});

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

// 监听“保存学习网站凭据”按钮点击事件
addCredentialButton.addEventListener('click', async () => {
    const websiteUrl = websiteUrlInput.value;
    const websiteName = websiteNameInput.value; // 新增：获取网站名称的值
    const taskName = taskNameInput.value; // 新增：获取任务名称的值
    const videoListUrl = videoListUrlInput.value; // 新增：获取视频列表URL的值
    const username = learningUsernameInput.value;
    const phoneNumber = learningPhoneNumberInput.value;
    const learningPassword = learningPasswordInput.value; // 新增：获取学习网站密码的值
    // const password = learningPasswordInput.value; // 移除密码字段
    // const passwordConfirm = learningPasswordConfirmInput.value; // 移除确认密码字段

    if (!websiteUrl) { // 只验证 websiteUrl
        alert('请填写完整的学习网站URL！');
        return;
    }

    // 移除密码一致性验证
    // if (password !== passwordConfirm) {
    //     alert('学习网站密码不一致！');
    //     return;
    // }

    alert('正在保存学习网站凭据...');

    try {
        const response = await authenticatedFetch('/api/credentials', {
            method: 'POST',
            body: JSON.stringify({
                website_url: websiteUrl,
                website_name: websiteName, // 新增：发送网站名称
                task_name: taskName, // 新增：发送任务名称
                video_list_url: videoListUrl, // 新增：发送视频列表URL
                learning_username: username, // 将 username 修改为 learning_username
                phone_number: phoneNumber,
                learning_password: learningPassword // 新增：发送学习网站密码
                // 移除密码和确认密码
                // password: password,
                // password_confirm: passwordConfirm
            })
        });

        const data = await response.json();
        // alert(data.message || '学习网站凭据保存成功！'); // 移除状态消息
        if (response.ok) {
            alert((data.message || '学习网站凭据保存成功！') + ' 正在跳转到主页...');
            setTimeout(() => { window.location.href = '/index'; }, 1500); // 1.5秒后跳转到主页
        } else {
            alert(`保存学习网站凭据失败: ${data.detail || data.message}`);
        }
    } catch (error) {
        alert('保存学习网站凭据请求失败: ' + error.message);
        console.error('Error:', error);
    }
});

// 监听“返回主页”按钮点击事件
backToIndexButton.addEventListener('click', () => {
    window.location.href = '/index'; // 返回主页
});

// 获取凭据信息以便编辑
async function fetchCredentialForEdit(id) {
    try {
        const response = await authenticatedFetch(`/api/credentials/${id}`, { method: 'GET' });
        if (response.ok) {
            const credential = await response.json();
            websiteUrlInput.value = credential.website_url;
            websiteNameInput.value = credential.website_name || ''; // 新增：回填网站名称
            taskNameInput.value = credential.task_name || ''; // 新增：回填任务名称
            videoListUrlInput.value = credential.video_list_url || '';
            learningUsernameInput.value = credential.learning_username || '';
            // 密码不回显，用户需要重新输入
            // learningPasswordInput.value = credential.learning_password || ''; 
        } else {
            const errorData = await response.json();
            alert(`加载凭据失败: ${errorData.detail || response.statusText}`); // 更新状态消息
        }
    } catch (error) {
        console.error('加载凭据失败:', error);
        alert('加载凭据失败，请检查网络或后端服务。' + error.message); // 更新状态消息
    }
}