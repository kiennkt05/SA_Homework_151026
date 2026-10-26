# Bài thực hành Database Design Pattern - Index Table

## Cấu trúc

```text
02-index-table-design-pattern/
├── lecture/                         # PDF bài giảng gốc
├── src/index_table_experiment.py    # Sinh dữ liệu, hai cách query, benchmark
├── tests/test_index_table_experiment.py
├── data/people.db                   # Sinh khi chạy, 10.000 bản ghi
└── results/
    ├── benchmark.json               # Số liệu máy đọc được
    └── RESULTS.md                   # Bảng kết quả benchmark
```

## Thực hiện

Yêu cầu Python 3.10 trở lên.

```powershell
python .\src\index_table_experiment.py
```

Mặc định chương trình tạo 10.000 bản ghi, seed `20261026`, rồi đo mỗi phương án 200 lần.

Tùy chỉnh:

```powershell
python .\src\index_table_experiment.py --records 10000 --iterations 500 --ward "Cầu Giấy"
```

Chạy kiểm thử:

```powershell
python -m unittest discover -s tests -v
```

## Tiêu chí đúng

- Fact table và index table đều có đúng 10.000 dòng.
- Mỗi địa chỉ có đúng ba thành phần, không rỗng.
- Dữ liệu `Cầu Giấy` xuất hiện ở nhiều tỉnh/thành phố để kiểm tra điều kiện “tỉnh/thành phố bất kỳ”.
- Baseline và Index Table trả đúng cùng danh sách ID.
- `EXPLAIN QUERY PLAN` xác nhận SQLite tìm `ward_index` bằng primary key.

## Kết quả thực nghiệm Index Table

- Số bản ghi fact table: **10000**
- Số bản ghi index table: **10000**
- Secondary key cần tìm: **Cầu Giấy**
- Số kết quả: **799**
- Số lần đo mỗi phương án: **200**
- Hai phương án trả cùng kết quả: **Có**

| Phương án | Mean (ms) | Median (ms) | P95 (ms) | Min (ms) | Max (ms) |
|---|---:|---:|---:|---:|---:|
| Baseline: full scan + vòng `for` | 45.7354 | 40.7986 | 83.5089 | 33.1411 | 119.3368 |
| Index Table: secondary key → reference | 5.5433 | 4.1620 | 10.1432 | 3.2374 | 13.2643 |

**Index Table nhanh hơn trung bình 8.25 lần.**