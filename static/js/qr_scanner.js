let html5QrCode = null;
let currentScanTarget = 'single';
let isCameraScanning = false;
let qrPreviewUrl = null;

function openQRScanner(target) {
    currentScanTarget = target;
    resetQRImageImport();
    bootstrap.Modal.getOrCreateInstance(document.getElementById('qrScannerModal')).show();
}

function getQRCodeReader() {
    if (!html5QrCode) {
        html5QrCode = new Html5Qrcode('qr-reader');
    }
    return html5QrCode;
}

function setQRUploadStatus(message, state = 'default') {
    const status = document.getElementById('qr-upload-status');
    status.textContent = message;
    status.dataset.state = state;
}

function resetQRImageImport() {
    const input = document.getElementById('qr-image-input');
    const preview = document.getElementById('qr-image-preview');
    const previewWrap = document.getElementById('qr-image-preview-wrap');
    const cameraPanel = document.getElementById('qr-camera-panel');
    const cameraButton = document.getElementById('qr-camera-button');

    if (!input || !preview || !previewWrap || !cameraPanel || !cameraButton) return;

    if (qrPreviewUrl) URL.revokeObjectURL(qrPreviewUrl);
    qrPreviewUrl = null;
    input.value = '';
    preview.removeAttribute('src');
    previewWrap.classList.add('d-none');
    cameraPanel.hidden = true;
    cameraButton.disabled = false;
    cameraButton.innerHTML = '<i class="fas fa-camera me-1" aria-hidden="true"></i>Dùng camera';
    setQRUploadStatus('Ảnh chỉ được đọc trên trình duyệt, không tải lên hệ thống.');
}

async function handleQRImageUpload(input) {
    const file = input.files && input.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
        setQRUploadStatus('Hãy chọn ảnh CCCD định dạng JPG, PNG hoặc WEBP.', 'error');
        return;
    }

    stopQRScannerCamera();
    const preview = document.getElementById('qr-image-preview');
    const previewWrap = document.getElementById('qr-image-preview-wrap');
    if (qrPreviewUrl) URL.revokeObjectURL(qrPreviewUrl);
    qrPreviewUrl = URL.createObjectURL(file);
    preview.src = qrPreviewUrl;
    previewWrap.classList.remove('d-none');
    setQRUploadStatus('Đang đọc mã QR từ ảnh…', 'loading');

    try {
        const decodedText = await getQRCodeReader().scanFile(file, true);
        onScanSuccess(decodedText);
    } catch (error) {
        console.warn('Không đọc được QR từ ảnh CCCD.', error);
        setQRUploadStatus('Chưa thấy mã QR. Hãy chọn ảnh rõ nét, đủ 4 góc CCCD và thử lại.', 'error');
    }
}

async function startQRScannerCamera() {
    const cameraPanel = document.getElementById('qr-camera-panel');
    const cameraButton = document.getElementById('qr-camera-button');
    if (isCameraScanning) return;

    resetQRImageImport();
    cameraPanel.hidden = false;
    cameraButton.disabled = true;
    cameraButton.innerHTML = '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>Đang mở camera';
    setQRUploadStatus('Cho phép trình duyệt sử dụng camera để quét trực tiếp.', 'loading');

    const config = {
        fps: 12,
        qrbox: (width, height) => {
            const size = Math.floor(Math.min(width, height) * 0.72);
            return { width: size, height: size };
        },
        aspectRatio: 1,
        experimentalFeatures: { useBarCodeDetectorIfSupported: true },
    };

    const reader = getQRCodeReader();
    try {
        await reader.start({ facingMode: 'environment' }, config, onScanSuccess, onScanFailure);
        isCameraScanning = true;
        cameraButton.innerHTML = '<i class="fas fa-camera me-1" aria-hidden="true"></i>Đang dùng camera';
        setQRUploadStatus('Đưa mã QR CCCD vào khung hình.', 'loading');
    } catch (rearCameraError) {
        try {
            await reader.start({ facingMode: 'user' }, config, onScanSuccess, onScanFailure);
            isCameraScanning = true;
            cameraButton.innerHTML = '<i class="fas fa-camera me-1" aria-hidden="true"></i>Đang dùng camera';
            setQRUploadStatus('Đưa mã QR CCCD vào khung hình.', 'loading');
        } catch (cameraError) {
            console.warn('Không thể mở camera để đọc QR.', cameraError);
            cameraPanel.hidden = true;
            cameraButton.disabled = false;
            cameraButton.innerHTML = '<i class="fas fa-camera me-1" aria-hidden="true"></i>Dùng camera';
            setQRUploadStatus('Không mở được camera. Hãy dùng chức năng tải ảnh CCCD.', 'error');
        }
    }
}

function stopQRScannerCamera() {
    if (!html5QrCode || !isCameraScanning) return;
    isCameraScanning = false;
    html5QrCode.stop().catch(error => console.warn('Không thể dừng camera QR.', error));
}

function closeQRScanner() {
    stopQRScannerCamera();
    bootstrap.Modal.getInstance(document.getElementById('qrScannerModal'))?.hide();
}

function onScanSuccess(decodedText) {
    const parts = decodedText.split('|');
    if (parts.length < 6) {
        setQRUploadStatus('Mã QR không đúng định dạng CCCD. Hãy kiểm tra lại ảnh.', 'error');
        return;
    }

    const cccd = parts[0].trim();
    const fullName = titleCase(parts[2].trim());
    const address = parts[5].trim();

    const targets = {
        single: ['bk-cccd', 'bk-name', 'bk-address'],
        group: ['group_cccd', 'group_name', 'group_address'],
        edit: ['edit-cccd', 'edit-customer', 'edit-address'],
    };
    const fields = targets[currentScanTarget];
    if (!fields || fields.some(id => !document.getElementById(id))) {
        setQRUploadStatus('Không tìm thấy biểu mẫu cần điền thông tin.', 'error');
        return;
    }

    document.getElementById(fields[0]).value = cccd;
    document.getElementById(fields[1]).value = fullName;
    document.getElementById(fields[2]).value = address;
    setQRUploadStatus(`Đã điền thông tin cho ${fullName}.`, 'success');
    stopQRScannerCamera();
    window.setTimeout(closeQRScanner, 550);
}

function onScanFailure() {
    // Việc không nhận được QR ở từng khung hình là bình thường, không hiển thị lỗi gây nhiễu.
}

function titleCase(value) {
    return value.toLowerCase().split(' ').filter(Boolean).map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}
