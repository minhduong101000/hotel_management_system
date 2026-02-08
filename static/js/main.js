document.addEventListener('DOMContentLoaded', () => {
    function tick() {
        const now = new Date();
        const time = now.toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit'});
        document.querySelectorAll('.js-clock').forEach(el => el.innerText = time);
    }
    setInterval(tick, 1000); tick();
});