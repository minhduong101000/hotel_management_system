/**
 * Escape dữ liệu người dùng trước khi ghép vào chuỗi HTML.
 * Dùng khi buộc phải dựng HTML bằng chuỗi; nơi nào đặt được textContent thì
 * ưu tiên textContent.
 */
function escapeHtml(value) {
    const holder = document.createElement('div');
    holder.textContent = value == null ? '' : String(value);
    return holder.innerHTML;
}

/**
 * Chọn phương thức nhận cọc trong các modal đặt phòng.
 * Giá trị lưu vào input ẩn để payload đọc được; nút được tô đậm để lễ tân thấy
 * mình đang chọn gì.
 */
function setDepositPaymentMethod(method, button, inputId) {
    const input = document.getElementById(inputId);
    if (input) input.value = method;
    const group = button?.closest('[role="group"]');
    if (group) {
        group.querySelectorAll('.pos-method-btn').forEach(b => {
            b.classList.toggle('active', b === button);
        });
    }
}

/**
 * Helper function: Xây dựng đúng API URL theo hotel_slug hiện tại.
 * Ví dụ: api('/api/rooms') -> '/central/rooms/api/rooms'
 *
 * Cách map URL:
 * /api/rooms* -> /<slug>/rooms/api/rooms*
 * /api/bookings* -> /<slug>/bookings/api/bookings*
 * /api/customers* -> /<slug>/customers/api/customers*
 * ... vv
 */
function api(path) {
    const slug = window.HOTEL_SLUG || '';
    if (!slug) return path; // Fallback nếu không có slug
    
    // --- XỬ LÝ ĐẶC BIỆT CHO TRÙNG LẶP PREFIX ---
    // Backend có 2 blueprint cùng dùng chung prefix /api/bookings/...
    // 1. timeline_bp: /api/bookings/timeline, /api/bookings/create, /api/bookings/<id>, ...
    // 2. booking_bp: /api/bookings/group_create, /api/bookings/update_services, ...
    
    // 1. BOOKING/ROOM SPECIALS (Ưu tiên cao nhất để tránh trùng lặp prefix)
    const bookingSpecials = [
        '/api/rooms/checkin',
        '/api/rooms/preview_checkout',
        '/api/rooms/checkout',
        '/api/orders/add',
        '/api/bookings/update_service_quantity',
        '/api/bookings/update_services'
    ];
    if (bookingSpecials.some(p => path.startsWith(p))) {
        return `/${slug}/bookings` + path;
    }

    if (path.startsWith('/api/bookings/calculate-price')) {
        return `/${slug}/rooms` + path;
    }

    // 2. TIMELINE SPECIALS
    const timelinePaths = [
        '/api/bookings/timeline',
        '/api/bookings/services-catalog',
        '/api/bookings/create',
        '/api/bookings/add-room',
        '/api/bookings/update_timeline',
        '/api/bookings/cancel',
        '/api/bookings/update',
        '/api/bookings/reschedule'
    ];
    if (timelinePaths.some(p => path.startsWith(p))) {
        return `/${slug}/timeline` + path;
    }
    // Pattern cho /api/bookings/<số id> (của timeline_bp)
    if (path.match(/^\/api\/bookings\/[0-9]+$/)) {
        return `/${slug}/timeline` + path;
    }

    // 4. MAPPING CHUNG (Duyệt theo object)
    const prefixMap = {
        '/api/reports/cashier': `/${slug}/cashier`,
        '/api/rooms': `/${slug}/rooms`,
        '/api/settings': `/${slug}/rooms`,
        '/api/bookings': `/${slug}/bookings`,
        '/api/booking': `/${slug}/bookings`,
        '/api/customers': `/${slug}/customers`,
        '/api/customer': `/${slug}/customers`,
        '/api/services': `/${slug}/services`,
        '/api/billing': `/${slug}/billing`,
        '/api/prices': `/${slug}/prices`,
        '/api/reports': `/${slug}/reports`,
        '/api/expenses': `/${slug}/expenses`,
        '/api/warehouse': `/${slug}/warehouse`,
    };

    for (const [apiPrefix, bpPrefix] of Object.entries(prefixMap)) {
        if (path.startsWith(apiPrefix)) {
            return bpPrefix + path;
        }
    }
    return '/' + slug + path; // Fallback generic
}

const nativeFetch = window.fetch.bind(window);
const csrfProtectedMethods = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function csrfFetch(input, options = {}) {
    const requestMethod = String(
        options.method || (input instanceof Request ? input.method : 'GET')
    ).toUpperCase();
    const requestUrl = new URL(
        typeof input === 'string' || input instanceof URL ? input : input.url,
        window.location.href
    );

    if (
        csrfProtectedMethods.has(requestMethod) &&
        requestUrl.origin === window.location.origin
    ) {
        const token = document.querySelector('meta[name="csrf-token"]')?.content;
        const headers = new Headers(
            options.headers || (input instanceof Request ? input.headers : undefined)
        );
        if (token) {
            headers.set('X-CSRFToken', token);
        }
        options = { ...options, headers };
    }

    return nativeFetch(input, options);
}

window.fetch = csrfFetch;

document.addEventListener('DOMContentLoaded', () => {
    function tick() {
        const now = new Date();
        const time = now.toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit'});
        document.querySelectorAll('.js-clock').forEach(el => el.innerText = time);
    }
    setInterval(tick, 1000); tick();

    const toggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('app-sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    const mobileSidebar = window.matchMedia('(max-width: 991.98px)');

    if (toggle && sidebar && backdrop) {
        function getSidebarFocusableElements() {
            return Array.from(sidebar.querySelectorAll('a[href], button:not([disabled])'))
                .filter(element => !element.hasAttribute('hidden'));
        }

        function openSidebar() {
            sidebar.inert = false;
            sidebar.classList.add('is-open');
            backdrop.hidden = false;
            document.body.classList.add('sidebar-open');
            toggle.setAttribute('aria-expanded', 'true');
            toggle.setAttribute('aria-label', 'Đóng menu điều hướng');

            const initialFocus = sidebar.querySelector('[aria-current="page"]')
                || sidebar.querySelector('a[href]');
            initialFocus?.focus();
        }

        function closeSidebar(restoreFocus = true) {
            sidebar.classList.remove('is-open');
            backdrop.hidden = true;
            document.body.classList.remove('sidebar-open');
            toggle.setAttribute('aria-expanded', 'false');
            toggle.setAttribute('aria-label', 'Mở menu điều hướng');
            sidebar.inert = mobileSidebar.matches;
            if (restoreFocus) toggle.focus();
        }

        function syncSidebarMode() {
            if (mobileSidebar.matches) {
                if (!sidebar.classList.contains('is-open')) sidebar.inert = true;
                return;
            }
            closeSidebar(false);
            sidebar.inert = false;
        }

        toggle.addEventListener('click', () => {
            if (sidebar.classList.contains('is-open')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });

        backdrop.addEventListener('click', () => closeSidebar());
        document.addEventListener('keydown', (event) => {
            if (!sidebar.classList.contains('is-open')) return;

            if (event.key === 'Escape') {
                closeSidebar();
                return;
            }

            if (event.key === 'Tab') {
                const focusableElements = getSidebarFocusableElements();
                const firstElement = focusableElements[0];
                const lastElement = focusableElements[focusableElements.length - 1];
                if (!firstElement || !lastElement) return;

                if (event.shiftKey && document.activeElement === firstElement) {
                    event.preventDefault();
                    lastElement.focus();
                } else if (!event.shiftKey && document.activeElement === lastElement) {
                    event.preventDefault();
                    firstElement.focus();
                }
            }
        });

        sidebar.querySelectorAll('a[href]').forEach(link => {
            link.addEventListener('click', () => {
                if (mobileSidebar.matches) closeSidebar(false);
            });
        });

        mobileSidebar.addEventListener('change', syncSidebarMode);
        syncSidebarMode();
    }
});
