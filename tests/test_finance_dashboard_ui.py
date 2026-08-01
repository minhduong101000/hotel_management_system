from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_revenue_chart_checks_data_before_chart_initialization():
    script = _source("static/js/revenue_report.js")

    assert "function hasRevenueChartData" in script
    assert "function hasOccupancyChartData" in script
    assert "if (!hasRevenueChartData(data.chart))" in script
    assert "if (!hasOccupancyChartData(data.chart))" in script
    assert "typeof Chart !== 'function'" in script
    assert "destroyRevenueChart()" in script
    assert "destroyOccupancyChart()" in script
    assert script.index("if (!hasRevenueChartData(data.chart))") < script.index("revenueChart = new Chart")
    assert script.index("if (!hasOccupancyChartData(data.chart))") < script.index("occupancyChart = new Chart")
    assert "revenue-chart-summary" in script
    assert "occupancy-chart-summary" in script


def test_revenue_uses_structured_states_safe_top_rooms_and_retry():
    script = _source("static/js/revenue_report.js")

    assert "renderFinanceState('revenue-chart-state', 'loading'" in script
    assert "renderFinanceState('revenue-chart-state', 'empty'" in script
    assert "renderFinanceState('revenue-chart-state', 'error'" in script
    assert "renderTopRoomsState('loading'" in script
    assert "renderTopRoomsState('empty'" in script
    assert "renderTopRoomsState('error'" in script
    assert "tbody.replaceChildren()" in script
    assert "document.createElement('tr')" in script
    assert "tbody.innerHTML" not in script
    assert "row.innerHTML" not in script
    assert "retry.addEventListener('click', () => loadRevenue())" in script


def test_cashier_renderer_is_safe_and_exposes_loading_validation_and_busy_state():
    script = _source("static/js/cashier_report.js")

    assert "renderCashierTableState('loading'" in script
    assert "renderCashierTableState('empty'" in script
    assert "renderCashierTableState('error'" in script
    assert "tbody.replaceChildren()" in script
    assert "document.createElement('tr')" in script
    assert "tbody.innerHTML" not in script
    assert "row.innerHTML" not in script
    assert "let cashierLoading = false" in script
    assert "if (cashierLoading) return" in script
    assert "setCashierLoadBusy(true)" in script
    assert "setCashierLoadBusy(false)" in script
    assert "showCashierFilterStatus" in script
    assert "showDepositPrintStatus" in script
    assert "alert(" not in script


def test_expense_renderer_options_save_and_void_are_safe_and_guarded():
    script = _source("static/js/expense_manager.js")

    assert "renderExpenseTableState('loading'" in script
    assert "renderExpenseTableState('empty'" in script
    assert "renderExpenseTableState('error'" in script
    assert "tbody.replaceChildren()" in script
    assert "document.createElement('option')" in script
    assert "tbody.innerHTML" not in script
    assert "row.innerHTML" not in script
    assert "select.innerHTML" not in script
    assert "let expenseSubmitting = false" in script
    assert "if (expenseSubmitting) return" in script
    assert "let expenseVoidSubmitting = false" in script
    assert "if (expenseVoidSubmitting) return" in script
    assert "setExpenseSubmitBusy(true)" in script
    assert "setExpenseVoidBusy(true)" in script
    assert "showExpenseFormStatus" in script
    assert "showExpenseVoidStatus" in script
    assert "api(`/api/expenses/${id}/void`)" in script
    assert "method: 'POST'" in script
    assert "alert(" not in script
