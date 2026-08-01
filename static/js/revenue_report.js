let revenueChart = null;
let occupancyChart = null;
let revenueLoading = false;

document.addEventListener('DOMContentLoaded', () => loadRevenue());

function fmtMoney(value) {
    const amount = Number(value);
    return Number.isFinite(amount) ? new Intl.NumberFormat('vi-VN').format(Math.round(amount)) : '0';
}

function createFinanceStateIcon(kind) {
    const icons = {
        loading: 'fas fa-circle-notch fa-spin',
        empty: 'fas fa-chart-column',
        error: 'fas fa-triangle-exclamation',
    };
    const wrapper = document.createElement('div');
    wrapper.className = 'data-state__icon';
    const icon = document.createElement('i');
    icon.className = icons[kind] || icons.empty;
    icon.setAttribute('aria-hidden', 'true');
    wrapper.appendChild(icon);
    return wrapper;
}

function renderFinanceState(stateId, kind, title, description, allowRetry = false) {
    const state = document.getElementById(stateId);
    const heading = document.createElement('h3');
    heading.className = 'data-state__title';
    heading.textContent = title;
    const message = document.createElement('p');
    message.className = 'data-state__description';
    message.textContent = description;
    state.className = `data-state data-state--${kind}`;
    state.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    state.replaceChildren(createFinanceStateIcon(kind), heading, message);

    if (allowRetry) {
        const actions = document.createElement('div');
        actions.className = 'data-state__actions button-group';
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.className = 'btn btn-outline-primary';
        const icon = document.createElement('i');
        icon.className = 'fas fa-rotate-right';
        icon.setAttribute('aria-hidden', 'true');
        const label = document.createElement('span');
        label.textContent = 'Thử tải lại';
        retry.append(icon, label);
        retry.addEventListener('click', () => loadRevenue());
        actions.appendChild(retry);
        state.appendChild(actions);
    }
}

function renderTopRoomsState(kind, title, description = '', allowRetry = false) {
    const tbody = document.getElementById('top-rooms-body');
    const row = document.createElement('tr');
    row.className = 'data-table-state-row';
    const cell = document.createElement('td');
    cell.colSpan = 5;
    const state = document.createElement('div');
    state.id = 'top-rooms-state';
    state.className = `data-state data-state--${kind}`;
    state.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    const heading = document.createElement('h3');
    heading.className = 'data-state__title';
    heading.textContent = title;
    const message = document.createElement('p');
    message.className = 'data-state__description';
    message.textContent = description;
    state.append(createFinanceStateIcon(kind), heading, message);
    if (allowRetry) {
        const actions = document.createElement('div');
        actions.className = 'data-state__actions button-group';
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.className = 'btn btn-outline-primary';
        retry.textContent = 'Thử tải lại';
        retry.addEventListener('click', () => loadRevenue());
        actions.appendChild(retry);
        state.appendChild(actions);
    }
    cell.appendChild(state);
    row.appendChild(cell);
    tbody.replaceChildren(row);
}

function showRevenueFeedback(message) {
    const feedback = document.getElementById('revenue-feedback');
    feedback.textContent = message;
    feedback.classList.toggle('d-none', !message);
}

function setRevenueLoadBusy(isBusy) {
    const button = document.getElementById('revenue-load-button');
    button.disabled = isBusy;
    button.setAttribute('aria-busy', String(isBusy));
    const icon = document.createElement('i');
    icon.className = isBusy ? 'fas fa-circle-notch fa-spin' : 'fas fa-chart-column';
    icon.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span');
    label.textContent = isBusy ? 'Đang tải' : 'Xem báo cáo';
    button.replaceChildren(icon, label);
}

function onPeriodChange() {
    const isCustom = document.getElementById('period-select').value === 'custom';
    document.getElementById('custom-range').classList.toggle('d-none', !isCustom);
    if (!isCustom) loadRevenue();
}

function buildRevenueUrl() {
    const period = document.getElementById('period-select').value;
    let url = api(`/api/reports/revenue?period=${period}`);
    if (period !== 'custom') return url;
    const start = document.getElementById('date-start').value;
    const end = document.getElementById('date-end').value;
    if (!start || !end) throw new Error('Vui lòng chọn đầy đủ từ ngày và đến ngày.');
    if (end < start) throw new Error('Đến ngày phải từ ngày bắt đầu trở đi.');
    return `${url}&start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;
}

function loadRevenue() {
    if (revenueLoading) return;
    let url;
    try {
        url = buildRevenueUrl();
    } catch (error) {
        showRevenueFeedback(error.message);
        return;
    }

    revenueLoading = true;
    setRevenueLoadBusy(true);
    showRevenueFeedback('');
    renderFinanceState('revenue-chart-state', 'loading', 'Đang tải biểu đồ tài chính', 'Vui lòng chờ trong giây lát.');
    renderFinanceState('occupancy-chart-state', 'loading', 'Đang tải tỉ lệ lấp đầy', 'Vui lòng chờ trong giây lát.');
    document.getElementById('revenue-chart-content').classList.add('d-none');
    document.getElementById('occupancy-chart-content').classList.add('d-none');
    renderTopRoomsState('loading', 'Đang tải xếp hạng phòng', 'Vui lòng chờ trong giây lát.');

    return fetch(url)
        .then(response => response.json().then(data => ({ok: response.ok, data})))
        .then(({ok, data: response}) => {
            if (!ok || !response.success) throw new Error(response.msg || 'Không thể tải báo cáo doanh thu.');
            const data = response.data;
            if (!data || !Array.isArray(data.chart) || !Array.isArray(data.top_rooms)) {
                throw new Error('Dữ liệu báo cáo không hợp lệ.');
            }
            renderRevenueOverview(data);
            renderRevenueChart(data);
            renderOccupancyChart(data);
            renderTopRooms(data.top_rooms);
        })
        .catch(error => {
            destroyRevenueChart();
            destroyOccupancyChart();
            document.getElementById('revenue-chart-content').classList.add('d-none');
            document.getElementById('occupancy-chart-content').classList.add('d-none');
            renderFinanceState('revenue-chart-state', 'error', 'Không thể tải biểu đồ tài chính', error.message, true);
            renderFinanceState('occupancy-chart-state', 'error', 'Không thể tải tỉ lệ lấp đầy', error.message, true);
            renderTopRoomsState('error', 'Không thể tải xếp hạng phòng', error.message, true);
            showRevenueFeedback(error.message);
        })
        .finally(() => {
            revenueLoading = false;
            setRevenueLoadBusy(false);
        });
}

function renderRevenueOverview(data) {
    document.getElementById('stat-revenue').textContent = `${fmtMoney(data.room_revenue)} đ`;
    document.getElementById('stat-cash').textContent = `${fmtMoney(data.total_net_payment)} đ`;
    document.getElementById('stat-expenses').textContent = `${fmtMoney(data.total_expenses)} đ`;
    document.getElementById('stat-profit').textContent = `${fmtMoney(data.net_profit)} đ`;
    const period = data.period || {};
    document.getElementById('report-period-label').textContent = period.start && period.end
        ? `Kỳ dữ liệu: ${period.start} – ${period.end}`
        : 'Kỳ dữ liệu hiện tại';
}

function hasRevenueChartData(chartRows) {
    return Array.isArray(chartRows) && chartRows.some(row => Number(row.revenue) !== 0 || Number(row.expense) !== 0);
}

function hasOccupancyChartData(chartRows) {
    return Array.isArray(chartRows) && chartRows.some(row => Number(row.occupancy_rate) > 0);
}

function destroyRevenueChart() {
    if (!revenueChart) return;
    revenueChart.destroy();
    revenueChart = null;
}

function destroyOccupancyChart() {
    if (!occupancyChart) return;
    occupancyChart.destroy();
    occupancyChart = null;
}

function renderRevenueChart(data) {
    destroyRevenueChart();
    const state = document.getElementById('revenue-chart-state');
    const content = document.getElementById('revenue-chart-content');
    if (!hasRevenueChartData(data.chart)) {
        content.classList.add('d-none');
        renderFinanceState('revenue-chart-state', 'empty', 'Chưa có doanh thu hoặc chi phí', 'Biểu đồ sẽ xuất hiện khi kỳ này có phát sinh tài chính.');
        return;
    }
    if (typeof Chart !== 'function') {
        content.classList.add('d-none');
        renderFinanceState('revenue-chart-state', 'error', 'Không thể mở biểu đồ', 'Thư viện biểu đồ chưa tải được.', true);
        return;
    }

    state.classList.add('d-none');
    content.classList.remove('d-none');
    const totalRevenue = data.chart.reduce((sum, row) => sum + Number(row.revenue || 0), 0);
    const totalExpense = data.chart.reduce((sum, row) => sum + Number(row.expense || 0), 0);
    document.getElementById('revenue-chart-summary').textContent = `Trong ${data.chart.length} ngày: doanh thu ${fmtMoney(totalRevenue)} đ, chi phí ${fmtMoney(totalExpense)} đ.`;
    revenueChart = new Chart(document.getElementById('revenueChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: data.chart.map(row => row.date),
            datasets: [
                {label: 'Doanh thu', data: data.chart.map(row => Number(row.revenue || 0)), backgroundColor: 'rgba(15, 118, 110, 0.72)', borderColor: '#0f766e', borderWidth: 1, borderRadius: 5},
                {label: 'Chi phí', data: data.chart.map(row => Number(row.expense || 0)), backgroundColor: 'rgba(220, 38, 38, 0.64)', borderColor: '#dc2626', borderWidth: 1, borderRadius: 5},
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {duration: 220},
            plugins: {legend: {position: 'top'}, tooltip: {callbacks: {label: context => `${context.dataset.label}: ${fmtMoney(context.parsed.y)} đ`}}},
            scales: {y: {beginAtZero: true, ticks: {callback: value => fmtMoney(value)}}},
        },
    });
}

function renderOccupancyChart(data) {
    destroyOccupancyChart();
    const state = document.getElementById('occupancy-chart-state');
    const content = document.getElementById('occupancy-chart-content');
    if (!hasOccupancyChartData(data.chart)) {
        content.classList.add('d-none');
        renderFinanceState('occupancy-chart-state', 'empty', 'Chưa có dữ liệu lấp đầy', 'Biểu đồ sẽ xuất hiện khi kỳ này có phòng được sử dụng.');
        return;
    }
    if (typeof Chart !== 'function') {
        content.classList.add('d-none');
        renderFinanceState('occupancy-chart-state', 'error', 'Không thể mở biểu đồ', 'Thư viện biểu đồ chưa tải được.', true);
        return;
    }

    state.classList.add('d-none');
    content.classList.remove('d-none');
    const average = Number(data.occupancy_rate || 0);
    document.getElementById('occupancy-chart-summary').textContent = `Tỉ lệ lấp đầy trung bình trong kỳ: ${average.toFixed(1)}%.`;
    occupancyChart = new Chart(document.getElementById('occupancyChart').getContext('2d'), {
        type: 'line',
        data: {
            labels: data.chart.map(row => row.date),
            datasets: [{label: 'Tỉ lệ lấp đầy (%)', data: data.chart.map(row => Number(row.occupancy_rate || 0)), borderColor: '#d97706', backgroundColor: 'rgba(217, 119, 6, 0.12)', borderWidth: 3, fill: true, tension: 0.28, pointRadius: 3}],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {duration: 220},
            plugins: {legend: {display: false}, tooltip: {callbacks: {label: context => `Tỉ lệ: ${context.parsed.y}%`}}},
            scales: {y: {beginAtZero: true, max: 100, ticks: {callback: value => `${value}%`}}},
        },
    });
}

function renderTopRooms(rooms) {
    if (!rooms.length) {
        renderTopRoomsState('empty', 'Chưa có phòng phát sinh doanh thu', 'Xếp hạng sẽ xuất hiện sau khi có phòng hoàn tất trong kỳ.');
        return;
    }
    const tbody = document.getElementById('top-rooms-body');
    tbody.replaceChildren();
    rooms.forEach((room, index) => {
        const row = document.createElement('tr');
        const rankCell = document.createElement('td');
        const rank = document.createElement('span');
        rank.className = `status-badge ${index === 0 ? 'status-badge--warning' : 'status-badge--neutral'}`;
        rank.textContent = `Top ${index + 1}`;
        rankCell.appendChild(rank);
        const numberCell = document.createElement('td');
        numberCell.className = 'fw-bold';
        numberCell.textContent = room.room_number || '-';
        const typeCell = document.createElement('td');
        typeCell.className = 'text-muted';
        typeCell.textContent = room.room_type || 'Chưa phân loại';
        const countCell = document.createElement('td');
        countCell.className = 'text-center numeric-tabular';
        countCell.textContent = Number(room.count || 0);
        const totalCell = document.createElement('td');
        totalCell.className = 'text-end numeric-tabular fw-bold finance-positive';
        totalCell.textContent = `${fmtMoney(room.total)} đ`;
        row.append(rankCell, numberCell, typeCell, countCell, totalCell);
        tbody.appendChild(row);
    });
}
