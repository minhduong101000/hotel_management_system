(function () {
    'use strict';

    const form = document.getElementById('login-form');
    const password = document.getElementById('password');
    const passwordToggle = document.getElementById('login-password-toggle');
    const submitButton = document.getElementById('login-submit');
    const submitLabel = submitButton?.querySelector('[data-login-submit-label]');
    const submitIcon = submitButton?.querySelector('[data-login-submit-icon]');
    const status = document.getElementById('login-form-status');

    if (password && passwordToggle) {
        passwordToggle.addEventListener('click', function () {
            const isVisible = password.type === 'text';
            password.type = isVisible ? 'password' : 'text';
            passwordToggle.setAttribute('aria-pressed', isVisible ? 'false' : 'true');
            passwordToggle.setAttribute('aria-label', isVisible ? 'Hiện mật khẩu' : 'Ẩn mật khẩu');

            const icon = passwordToggle.querySelector('[data-password-icon]');
            icon?.classList.toggle('fa-eye', isVisible);
            icon?.classList.toggle('fa-eye-slash', !isVisible);
        });
    }

    if (form && submitButton) {
        form.addEventListener('submit', function () {
            submitButton.disabled = true;
            submitButton.setAttribute('aria-busy', 'true');
            if (submitLabel) submitLabel.textContent = 'Đang đăng nhập...';
            if (submitIcon) submitIcon.className = 'fa-solid fa-circle-notch fa-spin';
            if (status) status.textContent = 'Đang xác thực tài khoản, vui lòng chờ.';
        });
    }
})();
