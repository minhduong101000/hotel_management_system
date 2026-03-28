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
        '/api/bookings/update_timeline',
        '/api/bookings/cancel',
        '/api/bookings/update'
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

document.addEventListener('DOMContentLoaded', () => {
    function tick() {
        const now = new Date();
        const time = now.toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit'});
        document.querySelectorAll('.js-clock').forEach(el => el.innerText = time);
    }
    setInterval(tick, 1000); tick();
});