document.addEventListener('DOMContentLoaded', () => {
    // 1. Chạy đồng hồ thời gian thực (cho các ô phòng trống)
    function updateClock() {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('vi-VN', {hour: '2-digit', minute:'2-digit'});
        
        // Tìm tất cả phần tử có class js-live-clock để cập nhật
        document.querySelectorAll('.js-live-clock').forEach(el => {
            el.innerText = timeStr;
        });
    }

    // Cập nhật mỗi giây
    setInterval(updateClock, 1000);
    updateClock(); // Chạy ngay lập tức
});