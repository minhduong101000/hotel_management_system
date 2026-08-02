(() => {
    const form = document.getElementById('master-login-form');
    const password = document.getElementById('master-password');
    const passwordToggle = document.getElementById('master-password-toggle');
    const submitButton = document.getElementById('master-login-submit');
    const status = document.getElementById('master-login-status');

    if (!form || !password || !passwordToggle || !submitButton || !status) return;

    passwordToggle.addEventListener('click', () => {
        const willShow = password.type === 'password';
        password.type = willShow ? 'text' : 'password';
        passwordToggle.setAttribute('aria-pressed', String(willShow));
        passwordToggle.setAttribute('aria-label', willShow ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
    });

    form.addEventListener('submit', () => {
        submitButton.disabled = true;
        submitButton.setAttribute('aria-busy', 'true');
        submitButton.querySelector('span').textContent = 'Đang đăng nhập…';
        status.textContent = 'Đang đăng nhập, vui lòng chờ.';
    });
})();
