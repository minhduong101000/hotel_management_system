(function () {
    const focusOrigins = new WeakMap();

    function focusElement(element) {
        if (!element || typeof element.focus !== 'function') return;
        element.focus({preventScroll: true});
    }

    function firstModalFocusTarget(modal) {
        const explicitTarget = modal.querySelector('[data-modal-initial-focus]');
        if (explicitTarget) return explicitTarget;
        return modal.querySelector(
            '.modal-title[tabindex="-1"], '
            + 'input:not([type="hidden"]):not([disabled]), '
            + 'select:not([disabled]), textarea:not([disabled]), '
            + 'button:not([disabled])'
        );
    }

    function findReplacementFocusOrigin(record) {
        if (record.element?.isConnected) return record.element;
        if (record.id) {
            const matchingId = document.getElementById(record.id);
            if (matchingId) return matchingId;
        }
        if (record.ariaLabel) {
            return Array.from(document.querySelectorAll('[aria-label]')).find(
                element => element.getAttribute('aria-label') === record.ariaLabel
            );
        }
        return null;
    }

    function bindModalAccessibility() {
        document.querySelectorAll('.modal').forEach(modal => {
            if (modal.dataset.accessibilityBound === '1') return;
            modal.dataset.accessibilityBound = '1';

            modal.addEventListener('show.bs.modal', event => {
                const origin = event.relatedTarget || document.activeElement;
                if (origin && !modal.contains(origin)) {
                    focusOrigins.set(modal, {
                        element: origin,
                        id: origin.id || '',
                        ariaLabel: origin.getAttribute?.('aria-label') || '',
                    });
                }
            });

            modal.addEventListener('shown.bs.modal', () => {
                focusElement(firstModalFocusTarget(modal));
            });

            modal.addEventListener('hidden.bs.modal', () => {
                const record = focusOrigins.get(modal);
                focusOrigins.delete(modal);
                if (!record) return;
                const origin = findReplacementFocusOrigin(record);
                const hiddenParent = origin?.closest?.('.modal:not(.show)');
                if (origin && !hiddenParent) {
                    focusElement(origin);
                }
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindModalAccessibility);
    } else {
        bindModalAccessibility();
    }

    function clearBookingFormError() {
        const modal = document.getElementById('bookingModal');
        const status = document.getElementById('booking-form-status');
        if (!modal || !status) return;
        status.textContent = '';
        status.classList.add('d-none');
        modal.querySelectorAll('[aria-invalid="true"]').forEach(control => {
            control.removeAttribute('aria-invalid');
            if (control.getAttribute('aria-describedby') === status.id) {
                control.removeAttribute('aria-describedby');
            }
        });
    }

    window.showBookingFormError = function (message, fieldId) {
        const status = document.getElementById('booking-form-status');
        const field = fieldId ? document.getElementById(fieldId) : null;
        if (!status) return;
        clearBookingFormError();
        status.textContent = message;
        status.classList.remove('d-none');
        if (field) {
            field.setAttribute('aria-invalid', 'true');
            field.setAttribute('aria-describedby', status.id);
            focusElement(field);
        } else {
            focusElement(status);
        }
    };

    window.beginBookingSubmission = function (statusName) {
        const modal = document.getElementById('bookingModal');
        if (!modal || modal.dataset.submitting === '1') return false;
        modal.dataset.submitting = '1';
        clearBookingFormError();
        modal.querySelectorAll('[data-booking-submit]').forEach(button => {
            button.dataset.idleHtml = button.innerHTML;
            button.disabled = true;
            const isCurrent = button.dataset.bookingSubmit === statusName;
            button.setAttribute('aria-busy', isCurrent ? 'true' : 'false');
            if (isCurrent) {
                button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Đang xử lý...';
            }
        });
        return true;
    };

    window.endBookingSubmission = function () {
        const modal = document.getElementById('bookingModal');
        if (!modal) return;
        modal.dataset.submitting = '0';
        modal.querySelectorAll('[data-booking-submit]').forEach(button => {
            button.disabled = false;
            button.setAttribute('aria-busy', 'false');
            if (button.dataset.idleHtml) {
                button.innerHTML = button.dataset.idleHtml;
                delete button.dataset.idleHtml;
            }
        });
    };
})();
