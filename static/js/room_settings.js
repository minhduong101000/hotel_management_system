let roomSettingsRooms = [];
let roomSettingsLoading = false;
let roomSettingsSubmitting = false;
let roomRateSubmitting = false;
const roomMaintenanceSubmitting = new Set();

document.addEventListener('DOMContentLoaded', () => {
    bindRoomSettingsEvents();
    loadRoomSettings();
});

function roomSettingsPage() {
    return document.getElementById('room-settings-page');
}

function canManageRoomStructure() {
    return roomSettingsPage()?.dataset.canManageStructure === 'true';
}

function bindRoomSettingsEvents() {
    document.getElementById('room-settings-refresh')?.addEventListener('click', loadRoomSettings);
    document.getElementById('add-room-button')?.addEventListener('click', openCreateRoomModal);
    document.getElementById('room-settings-search')?.addEventListener('input', renderFilteredRooms);
    document.getElementById('room-settings-type-filter')?.addEventListener('change', renderFilteredRooms);
    document.getElementById('room-settings-status-filter')?.addEventListener('change', renderFilteredRooms);
    document.getElementById('room-settings-form')?.addEventListener('submit', saveRoomSettings);
    document.getElementById('room-rate-form')?.addEventListener('submit', saveRoomRate);
}

function createRoomSettingsStateIcon(kind) {
    const icon = document.createElement('i');
    icon.className = {
        loading: 'fas fa-circle-notch fa-spin',
        empty: 'fas fa-bed',
        error: 'fas fa-triangle-exclamation',
    }[kind] || 'fas fa-bed';
    icon.setAttribute('aria-hidden', 'true');
    const wrapper = document.createElement('div');
    wrapper.className = 'data-state__icon';
    wrapper.appendChild(icon);
    return wrapper;
}

function createRoomSettingsStateRow(kind, title, description) {
    const row = document.createElement('tr');
    row.className = 'data-table-state-row';
    const cell = document.createElement('td');
    cell.colSpan = 5;
    const state = document.createElement('div');
    state.className = `data-state data-state--${kind}`;
    state.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    const heading = document.createElement('h3');
    heading.className = 'data-state__title';
    heading.textContent = title;
    const message = document.createElement('p');
    message.className = 'data-state__description';
    message.textContent = description;
    state.append(createRoomSettingsStateIcon(kind), heading, message);
    if (kind === 'error') {
        const retry = createRoomSettingsButton(
            'Thử tải lại cấu hình phòng',
            'fas fa-rotate-right',
            'btn-outline-primary',
            loadRoomSettings
        );
        const actions = document.createElement('div');
        actions.className = 'data-state__actions button-group';
        actions.appendChild(retry);
        state.appendChild(actions);
    }
    cell.appendChild(state);
    row.appendChild(cell);
    return row;
}

function createRoomSettingsButton(label, iconClass, variant, handler) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `btn btn-icon ${variant}`;
    button.setAttribute('aria-label', label);
    button.title = label;
    const icon = document.createElement('i');
    icon.className = iconClass;
    icon.setAttribute('aria-hidden', 'true');
    button.appendChild(icon);
    button.addEventListener('click', handler);
    return button;
}

function displayRoomStatus(room) {
    if (room.status === 'available' && room.clean_status === 'dirty') return 'dirty';
    return room.status || 'available';
}

function roomStatusLabel(status) {
    return {
        available: 'Sẵn sàng',
        occupied: 'Đang ở',
        maintenance: 'Bảo trì',
        dirty: 'Chờ dọn',
    }[status] || 'Chưa rõ';
}

function createStatusBadge(status) {
    const badge = document.createElement('span');
    badge.className = `status-badge status-badge--${status}`;
    badge.textContent = roomStatusLabel(status);
    return badge;
}

function formatRoomCurrency(value) {
    const amount = Number(value);
    return Number.isFinite(amount)
        ? new Intl.NumberFormat('vi-VN').format(amount)
        : '0';
}

function setRoomSettingsRefreshBusy(isBusy) {
    const button = document.getElementById('room-settings-refresh');
    if (!button) return;
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
}

async function loadRoomSettings() {
    if (roomSettingsLoading) return;
    roomSettingsLoading = true;
    setRoomSettingsRefreshBusy(true);
    renderRoomSettingsState('loading', 'Đang tải cấu hình phòng', 'Vui lòng chờ trong giây lát.');
    try {
        const data = await requestRoomSettingsJson(api('/api/settings'));
        if (!Array.isArray(data.rooms) || !Array.isArray(data.room_types)) {
            throw new Error('Dữ liệu cấu hình phòng không hợp lệ.');
        }
        roomSettingsRooms = data.rooms;
        renderRoomTypeOptions(data.room_types);
        renderFilteredRooms();
    } catch (error) {
        renderRoomSettingsState(
            'error',
            'Không thể tải cấu hình phòng',
            roomSettingsErrorMessage(error)
        );
    } finally {
        roomSettingsLoading = false;
        setRoomSettingsRefreshBusy(false);
    }
}

function renderRoomTypeOptions(types) {
    const filter = document.getElementById('room-settings-type-filter');
    const previous = filter.value;
    while (filter.options.length > 1) filter.remove(1);
    types.forEach(type => {
        const option = document.createElement('option');
        option.value = type;
        option.textContent = type;
        filter.appendChild(option);
    });
    if (types.includes(previous)) filter.value = previous;

    const datalist = document.getElementById('room-type-options');
    if (!datalist) return;
    datalist.replaceChildren();
    types.forEach(type => {
        const option = document.createElement('option');
        option.value = type;
        datalist.appendChild(option);
    });
}

function filteredRoomSettings() {
    const keyword = document.getElementById('room-settings-search').value.trim().toLowerCase();
    const roomType = document.getElementById('room-settings-type-filter').value;
    const status = document.getElementById('room-settings-status-filter').value;
    return roomSettingsRooms.filter(room => {
        const roomStatus = displayRoomStatus(room);
        const searchable = `${room.room_number} ${room.room_type}`.toLowerCase();
        return (
            (!keyword || searchable.includes(keyword))
            && (!roomType || room.room_type === roomType)
            && (!status || roomStatus === status)
        );
    });
}

function renderFilteredRooms() {
    const rooms = filteredRoomSettings();
    document.getElementById('room-settings-count').textContent = `${rooms.length} phòng`;
    if (!rooms.length) {
        renderRoomSettingsState(
            'empty',
            'Chưa có phòng phù hợp',
            'Hãy điều chỉnh bộ lọc hoặc thêm phòng mới.'
        );
        return;
    }

    const tbody = document.getElementById('room-settings-table');
    tbody.replaceChildren();
    rooms.forEach(room => tbody.appendChild(createRoomSettingsRow(room)));
}

function renderRoomSettingsState(kind, title, description) {
    const tbody = document.getElementById('room-settings-table');
    tbody.replaceChildren(createRoomSettingsStateRow(kind, title, description));
    document.getElementById('room-settings-count').textContent = '0 phòng';
}

function createRoomSettingsRow(room) {
    const row = document.createElement('tr');
    const roomCell = document.createElement('td');
    roomCell.className = 'ps-3 room-settings-room-cell';
    const roomNumber = document.createElement('strong');
    roomNumber.className = 'room-settings-room-number';
    roomNumber.textContent = `P.${room.room_number}`;
    const roomType = document.createElement('span');
    roomType.className = 'status-badge status-badge--neutral';
    roomType.textContent = room.room_type || 'Chưa phân loại';
    roomCell.append(roomNumber, roomType);

    const nightlyCell = document.createElement('td');
    nightlyCell.className = 'numeric-tabular fw-bold room-settings-price';
    nightlyCell.textContent = `${formatRoomCurrency(room.price_per_night)} đ`;

    const hourlyCell = document.createElement('td');
    hourlyCell.className = 'room-settings-hourly';
    const initial = document.createElement('span');
    initial.textContent = `Đầu ${room.initial_hours} giờ: ${formatRoomCurrency(room.price_initial_block)} đ`;
    const next = document.createElement('span');
    next.textContent = `Tiếp: ${formatRoomCurrency(room.price_next_hour)} đ/giờ`;
    hourlyCell.append(initial, next);

    const statusCell = document.createElement('td');
    const roomStatus = displayRoomStatus(room);
    statusCell.appendChild(createStatusBadge(roomStatus));
    if (Number(room.active_booking_count) > 0) {
        const notice = document.createElement('span');
        notice.className = 'room-settings-booking-notice';
        notice.textContent = `${room.active_booking_count} booking đang hoạt động`;
        statusCell.appendChild(notice);
    }

    const actionCell = document.createElement('td');
    actionCell.className = 'text-end pe-3';
    const actions = document.createElement('div');
    actions.className = 'table-row-actions button-group';
    actions.appendChild(createRoomSettingsButton(
        `Cập nhật giá phòng ${room.room_number}`,
        'fas fa-coins',
        'btn-outline-primary',
        () => openRateModal(room.id)
    ));
    if (canManageRoomStructure()) {
        const edit = createRoomSettingsButton(
            `Sửa cấu hình phòng ${room.room_number}`,
            'fas fa-pen',
            'btn-outline-secondary',
            () => openEditRoomModal(room.id)
        );
        edit.dataset.roomStructureAction = 'edit';
        const maintenance = createRoomSettingsButton(
            room.status === 'maintenance'
                ? `Kết thúc bảo trì phòng ${room.room_number}`
                : `Bật bảo trì phòng ${room.room_number}`,
            room.status === 'maintenance' ? 'fas fa-screwdriver-wrench' : 'fas fa-wrench',
            room.status === 'maintenance' ? 'btn-outline-success' : 'btn-outline-warning',
            () => changeRoomMaintenance(room.id)
        );
        maintenance.dataset.roomStructureAction = 'maintenance';
        actions.append(edit, maintenance);
    }
    actionCell.appendChild(actions);
    row.append(roomCell, nightlyCell, hourlyCell, statusCell, actionCell);
    return row;
}

function showRoomSettingsFeedback(message, kind = 'success') {
    const feedback = document.getElementById('room-settings-feedback');
    feedback.className = `alert alert-${kind}`;
    feedback.textContent = message;
}

function clearModalError(modalId, statusId) {
    const modal = document.getElementById(modalId);
    const status = document.getElementById(statusId);
    if (!modal || !status) return;
    status.textContent = '';
    status.classList.add('d-none');
    modal.querySelectorAll('[aria-invalid="true"]').forEach(control => {
        control.removeAttribute('aria-invalid');
        if (control.getAttribute('aria-describedby') === statusId) {
            control.removeAttribute('aria-describedby');
        }
    });
}

function showModalError(modalId, statusId, message, fieldId) {
    clearModalError(modalId, statusId);
    const status = document.getElementById(statusId);
    const field = fieldId ? document.getElementById(fieldId) : null;
    status.textContent = message;
    status.classList.remove('d-none');
    if (field) {
        field.setAttribute('aria-invalid', 'true');
        field.setAttribute('aria-describedby', statusId);
        field.focus();
    } else {
        status.focus();
    }
}

function openCreateRoomModal() {
    if (!canManageRoomStructure()) return;
    document.getElementById('room-settings-form').reset();
    document.getElementById('room-settings-id').value = '';
    document.getElementById('room-settings-modal-title-text').textContent = 'Thêm phòng';
    document.getElementById('room-maintenance-field').hidden = false;
    clearModalError('room-settings-modal', 'room-settings-form-status');
    bootstrap.Modal.getOrCreateInstance(
        document.getElementById('room-settings-modal')
    ).show();
}

function openEditRoomModal(roomId) {
    const room = roomSettingsRooms.find(item => item.id === roomId);
    if (!room || !canManageRoomStructure()) return;
    document.getElementById('room-settings-id').value = room.id;
    document.getElementById('room-number').value = room.room_number;
    document.getElementById('room-type').value = room.room_type;
    document.getElementById('room-price-night').value = room.price_per_night;
    document.getElementById('room-price-initial').value = room.price_initial_block;
    document.getElementById('room-initial-hours').value = room.initial_hours;
    document.getElementById('room-price-next').value = room.price_next_hour;
    document.getElementById('room-maintenance-field').hidden = true;
    document.getElementById('room-settings-modal-title-text').textContent = `Sửa phòng ${room.room_number}`;
    clearModalError('room-settings-modal', 'room-settings-form-status');
    bootstrap.Modal.getOrCreateInstance(
        document.getElementById('room-settings-modal')
    ).show();
}

function roomSettingsFormPayload() {
    return {
        room_number: document.getElementById('room-number').value.trim(),
        room_type: document.getElementById('room-type').value.trim(),
        price_per_night: document.getElementById('room-price-night').value,
        price_initial_block: document.getElementById('room-price-initial').value,
        initial_hours: document.getElementById('room-initial-hours').value,
        price_next_hour: document.getElementById('room-price-next').value,
    };
}

function setRoomSettingsSubmitBusy(isBusy) {
    const button = document.getElementById('room-settings-save');
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
    const icon = document.createElement('i');
    icon.className = isBusy ? 'fas fa-circle-notch fa-spin' : 'fas fa-save';
    icon.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span');
    label.textContent = isBusy ? 'Đang lưu' : 'Lưu phòng';
    button.replaceChildren(icon, label);
}

async function saveRoomSettings(event) {
    event.preventDefault();
    if (roomSettingsSubmitting) return;
    const id = document.getElementById('room-settings-id').value;
    const payload = roomSettingsFormPayload();
    if (!id) {
        payload.maintenance = document.getElementById('room-maintenance').checked;
    }
    roomSettingsSubmitting = true;
    setRoomSettingsSubmitBusy(true);
    clearModalError('room-settings-modal', 'room-settings-form-status');
    try {
        const endpoint = id ? `/api/settings/${id}` : '/api/settings';
        const method = id ? 'PUT' : 'POST';
        const data = await requestRoomSettingsJson(api(endpoint), {
            method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        bootstrap.Modal.getOrCreateInstance(
            document.getElementById('room-settings-modal')
        ).hide();
        showRoomSettingsFeedback(
            id ? 'Đã cập nhật cấu hình phòng.' : 'Đã thêm phòng mới.'
        );
        await loadRoomSettings();
        return data;
    } catch (error) {
        showRoomSettingsMutationError(
            error,
            'room-settings-modal',
            'room-settings-form-status',
            {
                room_number: 'room-number',
                room_type: 'room-type',
                price_per_night: 'room-price-night',
                price_initial_block: 'room-price-initial',
                initial_hours: 'room-initial-hours',
                price_next_hour: 'room-price-next',
            }
        );
    } finally {
        roomSettingsSubmitting = false;
        setRoomSettingsSubmitBusy(false);
    }
}

function openRateModal(roomId) {
    const room = roomSettingsRooms.find(item => item.id === roomId);
    if (!room) return;
    document.getElementById('room-rate-id').value = room.id;
    document.getElementById('room-rate-description').textContent = `Phòng ${room.room_number} · ${room.room_type}`;
    document.getElementById('rate-price-night').value = room.price_per_night;
    document.getElementById('rate-price-initial').value = room.price_initial_block;
    document.getElementById('rate-initial-hours').value = room.initial_hours;
    document.getElementById('rate-price-next').value = room.price_next_hour;
    clearModalError('room-rate-modal', 'room-rate-form-status');
    bootstrap.Modal.getOrCreateInstance(
        document.getElementById('room-rate-modal')
    ).show();
}

function setRoomRateSubmitBusy(isBusy) {
    const button = document.getElementById('room-rate-save');
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
    const icon = document.createElement('i');
    icon.className = isBusy ? 'fas fa-circle-notch fa-spin' : 'fas fa-save';
    icon.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span');
    label.textContent = isBusy ? 'Đang lưu' : 'Lưu giá';
    button.replaceChildren(icon, label);
}

async function saveRoomRate(event) {
    event.preventDefault();
    if (roomRateSubmitting) return;
    roomRateSubmitting = true;
    setRoomRateSubmitBusy(true);
    clearModalError('room-rate-modal', 'room-rate-form-status');
    const payload = {
        id: Number(document.getElementById('room-rate-id').value),
        price_per_night: document.getElementById('rate-price-night').value,
        price_initial_block: document.getElementById('rate-price-initial').value,
        initial_hours: document.getElementById('rate-initial-hours').value,
        price_next_hour: document.getElementById('rate-price-next').value,
    };
    try {
        await requestRoomSettingsJson(api('/api/prices/update-base'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        bootstrap.Modal.getOrCreateInstance(
            document.getElementById('room-rate-modal')
        ).hide();
        showRoomSettingsFeedback('Đã cập nhật giá mặc định.');
        await loadRoomSettings();
    } catch (error) {
        showRoomSettingsMutationError(
            error,
            'room-rate-modal',
            'room-rate-form-status',
            {
                price_per_night: 'rate-price-night',
                price_initial_block: 'rate-price-initial',
                initial_hours: 'rate-initial-hours',
                price_next_hour: 'rate-price-next',
            }
        );
    } finally {
        roomRateSubmitting = false;
        setRoomRateSubmitBusy(false);
    }
}

async function changeRoomMaintenance(roomId) {
    const room = roomSettingsRooms.find(item => item.id === roomId);
    if (!room || roomMaintenanceSubmitting.has(roomId)) return;
    const maintenance = room.status !== 'maintenance';
    if (Number(room.active_booking_count) > 0) {
        const action = maintenance ? 'bật bảo trì' : 'kết thúc bảo trì';
        const confirmed = window.confirm(
            `Phòng còn ${room.active_booking_count} booking đang hoạt động. Hệ thống không tự hủy hoặc dời booking. Bạn vẫn muốn ${action}?`
        );
        if (!confirmed) return;
    }
    roomMaintenanceSubmitting.add(roomId);
    try {
        const data = await requestRoomSettingsJson(
            api(`/api/settings/${roomId}/maintenance`),
            {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({maintenance}),
            }
        );
        showRoomSettingsFeedback(data.msg || 'Đã cập nhật trạng thái bảo trì.');
        await loadRoomSettings();
    } catch (error) {
        showRoomSettingsFeedback(roomSettingsErrorMessage(error), 'danger');
    } finally {
        roomMaintenanceSubmitting.delete(roomId);
    }
}

async function requestRoomSettingsJson(url, options = {}) {
    const response = await fetch(url, options);
    let data = {};
    try {
        data = await response.json();
    } catch (_error) {
        data = {};
    }
    if (!response.ok || data.success === false) {
        const error = new Error(data.msg || 'Không thể hoàn tất thao tác.');
        error.status = response.status;
        error.data = data;
        throw error;
    }
    return data;
}

function roomSettingsErrorMessage(error) {
    if (error.status === 400) return error.message || 'Dữ liệu chưa hợp lệ.';
    if (error.status === 403) return 'Bạn không có quyền thực hiện thao tác này.';
    if (error.status === 409) return error.message || 'Dữ liệu đang xung đột, vui lòng kiểm tra lại.';
    if (error instanceof TypeError) return 'Không thể kết nối máy chủ. Vui lòng thử lại.';
    return error.message || 'Đã xảy ra lỗi không xác định.';
}

function showRoomSettingsMutationError(error, modalId, statusId, fieldMap) {
    const errors = error.data?.errors || {};
    const firstField = Object.keys(errors)[0];
    const message = firstField ? errors[firstField] : roomSettingsErrorMessage(error);
    showModalError(modalId, statusId, message, fieldMap[firstField]);
}
