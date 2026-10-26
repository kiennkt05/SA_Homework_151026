# Bài tập: Thiết kế cho bảo mật bằng các design pattern.

## Kiến trúc

```text
Client
  |
  | :8080 - JWT + rate limit 10 req/s
  v
API Gateway
  |-- /users, /login ------------> User service :3001
  |-- /orders --------------------> Order service :3002
  |-- /dashboard --+-------------> User service
                   +-------------> Order service (song song)

Client -- PUT bằng URL ký sẵn, hết hạn 300 giây --> MinIO :9000
```

## Yêu cầu

| Yêu cầu | Thực hiện |
|---|---|
| Routing | Gateway chuyển `/users` sang User service và `/orders` sang Order service |
| Offloading | Gateway kiểm tra JWT HS256 và giới hạn 10 request/giây theo IP |
| Aggregation | `/dashboard` gọi User và Order song song, timeout 1,5 giây, có thể trả kết quả một phần với HTTP 206 |
| Valet Key | User service tạo pre-signed `PUT` URL đến MinIO, đúng một object và hết hạn sau 300 giây |
| Đo độ trễ | `scripts/benchmark.ps1` so sánh gọi thẳng và gọi qua gateway |

## Chạy hệ thống

Yêu cầu: Docker Desktop đang chạy.

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Tài khoản demo:

- Email: `admin@example.com`
- Mật khẩu: `admin123`
- MinIO Console: `http://localhost:9001`

Chạy toàn bộ kịch bản kiểm thử:

```powershell
.\scripts\demo.ps1
```

Đo độ trễ:

```powershell
.\scripts\benchmark.ps1
```

# Kết quả:

[TEST_RESULTS.md](TEST_RESULTS.md)
