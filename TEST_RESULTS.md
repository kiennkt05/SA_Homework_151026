# Báo cáo kết quả kiểm thử

- Môi trường: Windows, Docker Desktop 28.3.2, Docker Engine 28.3.2
- Lệnh chạy stack kiểm thử: `docker compose -f docker-compose.yml -f docker-compose.test.yml up --build -d`

## Kết quả chức năng và bảo mật

| STT | Ca kiểm thử | Kỳ vọng | Kết quả thực tế | Trạng thái |
|---:|---|---|---|:---:|
| 1 | Health của Gateway, User, Order và S3Mock | Các endpoint sẵn sàng | Gateway/User/Order trả JSON `status=ok`; S3Mock trả HTTP 200 | Đạt |
| 2 | Đăng nhập đúng tài khoản demo | HTTP 200, nhận JWT | Nhận JWT, TTL công bố 900 giây | Đạt |
| 3 | Cấu trúc JWT | HS256, issuer/audience đúng, TTL 900 giây | `alg=HS256`, `iss=security-patterns-homework`, `aud=api-gateway`, TTL=900 | Đạt |
| 4 | Đăng nhập sai mật khẩu | HTTP 401 | HTTP 401, `Invalid credentials` | Đạt |
| 5 | Gọi API thiếu Bearer token | HTTP 401 | HTTP 401, `Bearer token is required` | Đạt |
| 6 | Gọi API bằng token hỏng | HTTP 401 | HTTP 401, `Invalid or expired token` | Đạt |
| 7 | Routing `/users/1` qua Gateway | HTTP 200, đúng user | Trả user id `1`, không lộ password | Đạt |
| 8 | Routing `/orders?userId=1` qua Gateway | HTTP 200, đúng danh sách | Trả 2 order của user `1` | Đạt |
| 9 | Truy cập user khác | HTTP 403 | HTTP 403 | Đạt |
| 10 | Truy cập orders của user khác | HTTP 403 | HTTP 403 | Đạt |
| 11 | Truy cập dashboard của user khác | HTTP 403 | HTTP 403 | Đạt |
| 12 | Gọi trực tiếp User service không có trusted identity | HTTP 401 | HTTP 401 | Đạt |
| 13 | Gọi trực tiếp Order service không có trusted identity | HTTP 401 | HTTP 401 | Đạt |
| 14 | Aggregation `/dashboard` khi hai service hoạt động | HTTP 200, dữ liệu đầy đủ | `partial=false`, có user và 2 orders | Đạt |
| 15 | Aggregation khi Order service dừng | HTTP 206, dữ liệu một phần | `partial=true`, user còn nguyên, orders rỗng, lỗi `orders=unavailable` | Đạt |
| 16 | Tạo order hợp lệ và gửi giả `userId=2` trong body | HTTP 201, server ép userId theo JWT | HTTP 201, order trả về có `userId=1` | Đạt |
| 17 | Tạo order thiếu dữ liệu hợp lệ | HTTP 400 | HTTP 400 | Đạt |
| 18 | Xin Valet Key với MIME hợp lệ | PUT, đúng object, hết hạn 300 giây | `method=PUT`, `X-Amz-Expires=300`, path khớp object key, Content-Type khớp | Đạt |
| 19 | Upload trực tiếp bằng URL ký sẵn | Upload thành công, không đi qua Gateway | PUT tới S3Mock thành công | Đạt* |
| 20 | Xin Valet Key với MIME không cho phép | HTTP 400 | HTTP 400 | Đạt |
| 21 | Rate limit 12 request nhanh | 10 request đầu HTTP 200; request 11–12 HTTP 429 | Đúng kỳ vọng | Đạt |
| 22 | JSON vượt giới hạn 100 KB | HTTP 413 | HTTP 413 | Đạt |
| 23 | Route không tồn tại | HTTP 404 | HTTP 404 | Đạt |
| 24 | Ẩn dấu vết framework | Không có `X-Powered-By` | Header không xuất hiện | Đạt |

## Kết quả đo độ trễ

| Đường gọi | Số request | Trung bình | P95 | Min | Max |
|---|---:|---:|---:|---:|---:|
| Direct → User service (`127.0.0.1`) | 10 | 3,82 ms | 13,01 ms | 2,43 ms | 13,01 ms |
| Client → Gateway → User service (`127.0.0.1`) | 10 | 7,40 ms | 11,03 ms | 6,46 ms | 11,03 ms |