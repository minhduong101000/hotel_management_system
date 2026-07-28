# Quy tắc làm việc của project

- Mọi kết luận về mã nguồn phải dựa trên việc kiểm tra trực tiếp code; không suy đoán khi chưa có bằng chứng.
- Nếu yêu cầu, hành vi hiện có, hoặc phạm vi thay đổi còn mơ hồ, phải hỏi và chờ người dùng xác nhận trước khi triển khai.
- Không tự ý thêm tính năng hoặc mở rộng phạm vi ngoài phần người dùng đã cho phép.
- Mọi thay đổi chức năng hoặc sửa lỗi phải áp dụng TDD: viết test thất bại trước, triển khai tối thiểu để test qua, refactor, rồi chạy lại test.
- Trước khi báo hoàn tất, phải chạy kiểm tra phù hợp và nêu rõ phần đã kiểm chứng cũng như phần chưa thể kiểm chứng.
- Không dùng thao tác phá hủy hoặc làm mất thay đổi hiện có của người dùng.
- Mọi spec, implementation plan, và tài liệu hướng dẫn mới của project phải viết bằng tiếng Việt rõ ràng; chỉ giữ thuật ngữ kỹ thuật tiếng Anh khi cần thiết.
- Với mọi thay đổi giao diện, trước khi báo hoàn tất phải dùng `bb-browser` để kiểm tra trực quan các luồng đã thay đổi ở trạng thái desktop phù hợp. Nếu `bb-browser` không khả dụng trong môi trường, phải báo rõ đây là phần chưa thể kiểm chứng; không được tuyên bố UI đã hoàn tất kiểm tra.
- Mọi commit mới phải dùng commit message bằng tiếng Anh; không tự ý sửa lại lịch sử commit đã tạo chỉ để đổi ngôn ngữ.
- Khi hoàn thành một hạng mục độc lập và các kiểm tra phù hợp đã xanh, phải tạo commit riêng ngay; không trộn phần đang dở hoặc thay đổi không liên quan vào commit đó.
- Không báo tiến độ hoặc bàn giao một phần chức năng đang dở. Mỗi lần triển khai phải hoàn tất trọn một hạng mục độc lập theo TDD (test đỏ, triển khai, test xanh, kiểm tra phù hợp, commit riêng) rồi mới báo cho người dùng; nếu bị chặn phải nêu rõ điểm chặn và không trình bày phần dang dở như đã hoàn thành.
- Với mọi việc đánh giá, thiết kế hoặc thay đổi giao diện/UI-UX, phải dùng skill `ui-ux-pro-max` để định hướng về cấu trúc, tính nhất quán, khả năng truy cập và trải nghiệm thao tác; không tự suy đoán quyết định thiết kế khi chưa kiểm tra code và yêu cầu nghiệp vụ.
