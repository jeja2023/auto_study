// 获取系统认证界面元素 (旧的，将移除或替换)
// const systemAuthSection = document.getElementById('systemAuthSection');
// const systemUsernameInput = document.getElementById('systemUsername');
// const systemPhoneNumberInput = document.getElementById('systemPhoneNumber');
// const systemPasswordInput = document.getElementById('systemPassword');
// const systemPasswordConfirmInput = document.getElementById('systemPasswordConfirm');

// 获取新添加的元素
const showRegisterButton = document.getElementById('showRegister');
const showLoginButton = document.getElementById('showLogin');
const registerSection = document.getElementById('registerSection');
const loginSection = document.getElementById('loginSection');

// 注册表单元素
const regUsernameInput = document.getElementById('regUsername');
const regPhoneNumberInput = document.getElementById('regPhoneNumber');
const regPasswordInput = document.getElementById('regPassword');
const regPasswordConfirmInput = document.getElementById('regPasswordConfirm');
const registerButton = document.getElementById('registerButton'); // 注册按钮

// 登录表单元素
const loginUsernameOrPhoneInput = document.getElementById('loginUsernameOrPhone');
const loginPasswordInput = document.getElementById('loginPassword');
const loginSystemButton = document.getElementById('loginSystemButton'); // 登录按钮

// 切换注册/登录区块的函数
function showAuthSection(section) {
    if (section === 'register') {
        registerSection.style.display = 'block';
        loginSection.style.display = 'none';
        showRegisterButton.classList.add('active');
        showLoginButton.classList.remove('active');
    } else {
        registerSection.style.display = 'none';
        loginSection.style.display = 'block';
        showLoginButton.classList.add('active');
        showRegisterButton.classList.remove('active');
    }
}

// 默认显示登录区块
showAuthSection('login');

// 切换按钮的事件监听器
showRegisterButton.addEventListener('click', () => showAuthSection('register'));
showLoginButton.addEventListener('click', () => showAuthSection('login'));

// --- 系统用户认证逻辑 (更新后的) ---

// 监听“注册”按钮点击事件
registerButton.addEventListener('click', async () => {
    const username = regUsernameInput.value;
    const phoneNumber = regPhoneNumberInput.value;
    const password = regPasswordInput.value;
    const passwordConfirm = regPasswordConfirmInput.value;

    if (!password || !passwordConfirm) {
        alert('注册时密码和确认密码不能为空！'); // 使用 alert 替代
        return;
    }
    if (password !== passwordConfirm) {
        alert('注册时两次输入的密码不一致！'); // 使用 alert 替代
        return;
    }
    if (!username) {
        alert('注册时用户名不能为空！'); // 使用 alert 替代
        return;
    }
    if (!phoneNumber) {
        alert('注册时手机号码不能为空！'); // 使用 alert 替代
        return;
    }

    try {
        const response = await fetch('/api/users/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                phone_number: phoneNumber,
                password: password,
                passwordConfirm: passwordConfirm
            })
        });

        const data = await response.json();
        if (response.ok) {
            alert(data.message || '系统用户注册成功！请登录。'); // 使用 alert 替代
            // 注册成功后自动切换到登录界面
            showAuthSection('login');
            // 可以在这里预填充登录表单，但为了简单起见暂时不添加
            loginUsernameOrPhoneInput.value = username || phoneNumber; // 预填充用户名或手机号
        } else {
            alert(`注册失败: ${data.detail || data.message}`); // 使用 alert 替代
        }
    } catch (error) {
        alert('注册请求失败: ' + error.message); // 使用 alert 替代
        console.error('Error:', error);
    }
});

// 监听“登录”按钮点击事件
loginSystemButton.addEventListener('click', async () => {
    const usernameOrPhone = loginUsernameOrPhoneInput.value; 
    const password = loginPasswordInput.value;

    if (!usernameOrPhone || !password) {
        alert('登录时用户名/手机号码和密码不能为空！'); // 使用 alert 替代
        return;
    }

    try {
        const formBody = new URLSearchParams();
        formBody.append('username', usernameOrPhone);
        formBody.append('password', password);

        const response = await fetch('/api/users/token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: formBody.toString()
        });

        const data = await response.json();
        if (response.ok) {
            localStorage.setItem('authToken', data.access_token);
            // alert('系统登录成功！正在跳转...'); // 移除此行，避免额外提示
            window.location.href = '/index'; 
        } else {
            alert(`系统登录失败: ${data.detail || data.message}`); // 使用 alert 替代
        }
    } catch (error) {
        alert('系统登录请求失败: ' + error.message); // 使用 alert 替代
        console.error('Error:', error);
    }
});