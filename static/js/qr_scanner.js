let html5QrCode = null;
let currentScanTarget = 'single'; // 'single', 'group', or 'edit'

function openQRScanner(target) {
    currentScanTarget = target;
    const scannerModalElement = document.getElementById('qrScannerModal');
    const scannerModal = new bootstrap.Modal(scannerModalElement);
    scannerModal.show();
    
    // Đợi modal CSS transition xong mới init camera
    setTimeout(() => {
        if (!html5QrCode) {
            html5QrCode = new Html5Qrcode("qr-reader");
        }
        
        // Tối ưu cấu hình để nhận diện mã QR mật độ cao (như trên CCCD)
        const config = { 
            fps: 20, // Tăng fps để bắt hình mượt hơn
            qrbox: function(viewfinderWidth, viewfinderHeight) {
                let minEdgePercentage = 0.7; // Chiếm 70% khung hình
                let minEdgeSize = Math.min(viewfinderWidth, viewfinderHeight);
                let qrboxSize = Math.floor(minEdgeSize * minEdgePercentage);
                return {
                    width: qrboxSize,
                    height: qrboxSize
                };
            },
            aspectRatio: 1.0,
            experimentalFeatures: {
                useBarCodeDetectorIfSupported: true // Sử dụng tính năng phần cứng nếu có
            }
        };
        
        // Ưu tiên CAMERA SAU (facingMode: "environment") theo yêu cầu người dùng
        html5QrCode.start(
            { facingMode: "environment" }, 
            config, 
            onScanSuccess, 
            onScanFailure
        ).then(() => {
            // Sau khi start thành công, thử bật tính năng AUTO-FOCUS nâng cao nếu trình duyệt hỗ trợ
            const track = html5QrCode.getRunningTrack();
            if (track && track.applyConstraints) {
                const capabilities = track.getCapabilities();
                const constraints = {};
                
                // Nếu hỗ trợ chế độ lấy nét liên tục (Continuous Focus)
                if (capabilities.focusMode && capabilities.focusMode.includes('continuous')) {
                    constraints.focusMode = 'continuous';
                }
                
                // Nếu hỗ trợ zoom (đôi khi zoom nhẹ giúp focus tốt hơn ở khoảng cách gần)
                // Tuy nhiên ta ưu tiên focus trước
                
                if (Object.keys(constraints).length > 0) {
                    track.applyConstraints({ advanced: [constraints] })
                        .then(() => console.log("Đã bật Auto-focus nâng cao."))
                        .catch(err => console.warn("Không thể áp dụng cấu hình focus: ", err));
                }
            }
        }).catch(err => {
            console.error("Lỗi khởi tạo camera sau: ", err);
            // Nếu lỗi (có thể là PC/Laptop chỉ có cam trước), thử quét cam trước
            html5QrCode.start(
                { facingMode: "user" }, 
                config, 
                onScanSuccess
            ).catch(err2 => {
                alert("Không thể khởi động Camera: " + err2);
            });
        });
    }, 500);
}

function closeQRScanner() {
    if (html5QrCode) {
        html5QrCode.stop().then(() => {
            console.log("Camera stopped.");
        }).catch(err => {
            console.error("Camera stop error: ", err);
        });
    }
    const scannerModal = bootstrap.Modal.getInstance(document.getElementById('qrScannerModal'));
    if (scannerModal) {
        scannerModal.hide();
    }
}

function onScanSuccess(decodedText, decodedResult) {
    // Format CCCD Việt Nam: 048000000001|123456789|NGUYEN VAN A|01012000|Nam|Ha Noi|01012021
    const parts = decodedText.split('|');
    console.log("QR Scanned Parts: ", parts);
    
    // CCCD hợp lệ thường có 7 phần phân cách bởi '|' hoặc ít nhất là có độ dài nhất định
    if (parts.length >= 6) {
        const cccd_num = parts[0].trim();
        const full_name = titleCase(parts[2].trim());
        const address = parts[5].trim();
        
        // Auto fill HTML
        if (currentScanTarget === 'single') {
            document.getElementById('bk-cccd').value = cccd_num;
            document.getElementById('bk-name').value = full_name;
            document.getElementById('bk-address').value = address;
        } else if (currentScanTarget === 'group') {
            document.getElementById('group_cccd').value = cccd_num;
            document.getElementById('group_name').value = full_name;
            document.getElementById('group_address').value = address;
        } else if (currentScanTarget === 'edit') {
            document.getElementById('edit-cccd').value = cccd_num;
            document.getElementById('edit-customer').value = full_name;
            document.getElementById('edit-address').value = address;
        }
        
        // Phát âm thanh bíp và đóng form
        alert(`Đã quét thành công CCCD: ${full_name}`);
        closeQRScanner();
    } else {
        alert("Mã QR không hợp lệ (Không đúng định dạng CCCD).");
    }
}

function onScanFailure(error) {
    // handle scan failure, usually better to ignore and keep scanning.
    // console.warn(`Code scan error = ${error}`);
}

// Hàm chuẩn hóa viết hoa chữ cái đầu: NGUYEN VAN A -> Nguyen Van A
function titleCase(str) {
    return str.toLowerCase().split(' ').map(function(word) {
        return (word.charAt(0).toUpperCase() + word.slice(1));
    }).join(' ');
}
