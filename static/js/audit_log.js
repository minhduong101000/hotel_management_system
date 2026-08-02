(() => {
    const list = document.getElementById('audit-list');
    const pagination = document.getElementById('audit-pagination');
    const summary = document.getElementById('audit-summary');
    const feedback = document.getElementById('audit-feedback');
    const filterButton = document.getElementById('audit-filter');
    const refreshButton = document.getElementById('audit-refresh');

    if (!list || !pagination || !summary || !feedback || !filterButton || !refreshButton) return;

    const labels = {
        checkin: 'Check-in',
        checkout: 'Checkout',
        create_booking: 'Tạo đặt phòng',
        create_group_booking: 'Tạo đặt phòng đoàn',
        update_booking_timeline: 'Cập nhật timeline',
        reschedule_booking_keep_price: 'Dời lịch - giữ giá',
        reschedule_booking_reprice: 'Dời lịch - áp dụng giá mới',
        cancel_booking: 'Hủy phòng',
        group_checkout: 'Checkout đoàn',
        add_booking_order: 'Gọi thêm dịch vụ',
        update_booking_service_quantity: 'Cập nhật số lượng dịch vụ',
        update_group_booking_services: 'Cập nhật dịch vụ đoàn',
        clean_room: 'Dọn phòng',
        restock_inventory: 'Nhập kho',
        create_inventory: 'Tạo vật tư',
        update_inventory: 'Cập nhật vật tư',
        delete_inventory: 'Xóa vật tư',
        update_base_price: 'Cập nhật giá phòng',
        create_price_rule: 'Tạo luật giá',
        update_price_rule: 'Cập nhật luật giá',
        delete_price_rule: 'Xóa luật giá',
        create_expense: 'Tạo chi phí',
        delete_expense: 'Xóa chi phí',
        create_staff_user: 'Tạo nhân sự',
        reset_staff_password: 'Đặt lại mật khẩu nhân sự',
        delete_staff_user: 'Xóa nhân sự',
        booking: 'Đặt phòng',
        booking_room: 'Phòng đặt',
        booking_service: 'Dịch vụ phòng',
        inventory_item: 'Hàng trong kho',
        room: 'Phòng',
        price_rule: 'Luật giá',
        expense: 'Chi phí',
        user: 'Nhân sự'
    };

    let currentPage = 1;
    let auditLoading = false;

    function filters() {
        return {
            start: document.getElementById('audit-start').value,
            end: document.getElementById('audit-end').value,
            group: document.getElementById('audit-group').value,
            action: document.getElementById('audit-action').value.trim(),
            entity_type: document.getElementById('audit-entity').value.trim()
        };
    }

    function setAuditBusy(isBusy) {
        auditLoading = isBusy;
        [filterButton, refreshButton].forEach(button => {
            button.disabled = isBusy;
            button.setAttribute('aria-busy', String(isBusy));
        });
        feedback.textContent = isBusy ? 'Đang cập nhật nhật ký…' : '';
    }

    function createStateCell(state, title, description) {
        const cell = document.createElement('td');
        cell.colSpan = 5;
        const stateBox = document.createElement('div');
        stateBox.className = `data-state data-state--${state}`;
        stateBox.setAttribute('role', state === 'error' ? 'alert' : 'status');

        const icon = document.createElement('div');
        icon.className = 'data-state__icon';
        const iconElement = document.createElement('i');
        iconElement.className = state === 'loading'
            ? 'fas fa-spinner fa-spin'
            : state === 'error' ? 'fas fa-triangle-exclamation' : 'fas fa-clock-rotate-left';
        iconElement.setAttribute('aria-hidden', 'true');
        icon.appendChild(iconElement);

        const heading = document.createElement('h3');
        heading.className = 'data-state__title';
        heading.textContent = title;
        const message = document.createElement('p');
        message.className = 'data-state__description';
        message.textContent = description;
        stateBox.append(icon, heading, message);
        cell.appendChild(stateBox);
        return cell;
    }

    function renderAuditTableState(state, description = '') {
        list.replaceChildren();
        const row = document.createElement('tr');
        row.className = 'data-table-state-row';
        const content = {
            loading: ['Đang tải nhật ký', 'Vui lòng chờ trong giây lát.'],
            empty: ['Chưa có thao tác phù hợp', 'Thử thay đổi bộ lọc hoặc khoảng thời gian.'],
            error: ['Không thể tải nhật ký', description || 'Vui lòng thử lại sau.']
        }[state];
        row.appendChild(createStateCell(state, content[0], content[1]));
        list.appendChild(row);
    }

    function createTextCell(text, className = '') {
        const cell = document.createElement('td');
        cell.textContent = text;
        if (className) cell.className = className;
        return cell;
    }

    function renderRows(items) {
        list.replaceChildren();
        if (!items.length) {
            renderAuditTableState('empty');
            return;
        }

        items.forEach(item => {
            const row = document.createElement('tr');
            row.appendChild(createTextCell(new Date(item.created_at).toLocaleString('vi-VN'), 'text-nowrap small'));
            row.appendChild(createTextCell(item.actor_name || 'Hệ thống', 'fw-semibold'));

            const actionCell = document.createElement('td');
            const badge = document.createElement('span');
            badge.className = 'status-badge status-badge--info';
            badge.textContent = labels[item.action] || item.action;
            actionCell.appendChild(badge);
            row.appendChild(actionCell);

            row.appendChild(createTextCell(`${labels[item.entity_type] || item.entity_type} #${item.entity_id ?? '—'}`));

            const detailCell = document.createElement('td');
            detailCell.className = 'text-end audit-detail-cell';
            const details = document.createElement('details');
            const detailsSummary = document.createElement('summary');
            detailsSummary.className = 'btn btn-outline-secondary audit-detail-toggle';
            detailsSummary.textContent = 'Xem dữ liệu';
            const data = document.createElement('pre');
            data.className = 'audit-detail-data text-start';
            data.textContent = JSON.stringify({ trước: item.before_data, sau: item.after_data }, null, 2);
            details.append(detailsSummary, data);
            detailCell.appendChild(details);
            row.appendChild(detailCell);
            list.appendChild(row);
        });
    }

    function renderPagination(data) {
        pagination.replaceChildren();
        if (data.total_pages <= 1) return;
        const controls = document.createElement('div');
        controls.className = 'btn-group';
        const pageDefinitions = [
            [data.page - 1, '‹', 'Trang trước'],
            [data.page + 1, '›', 'Trang sau']
        ];
        pageDefinitions.forEach(([page, text, label], index) => {
            if (index === 1) {
                const current = document.createElement('span');
                current.className = 'btn btn-outline-secondary disabled';
                current.textContent = `Trang ${data.page}/${data.total_pages}`;
                controls.appendChild(current);
            }
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn btn-outline-secondary';
            button.textContent = text;
            button.setAttribute('aria-label', label);
            button.disabled = page < 1 || page > data.total_pages;
            button.addEventListener('click', () => load(page));
            controls.appendChild(button);
        });
        pagination.appendChild(controls);
    }

    async function load(page = 1) {
        if (auditLoading) return;
        currentPage = page;
        setAuditBusy(true);
        renderAuditTableState('loading');
        const query = new URLSearchParams({ page: String(page), per_page: '25' });
        Object.entries(filters()).forEach(([key, value]) => {
            if (value) query.set(key, value);
        });

        try {
            const response = await fetch(`api/events?${query}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Không thể tải nhật ký.');
            renderRows(data.items || []);
            summary.textContent = `${data.total || 0} thao tác phù hợp`;
            renderPagination(data);
        } catch (error) {
            renderAuditTableState('error', error.message);
            summary.textContent = '';
            pagination.replaceChildren();
            feedback.textContent = error.message;
        } finally {
            setAuditBusy(false);
        }
    }

    filterButton.addEventListener('click', () => load(1));
    refreshButton.addEventListener('click', () => load(currentPage));
    load();
})();
