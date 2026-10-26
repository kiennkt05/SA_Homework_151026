# Kết quả thực nghiệm Index Table

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

## Query plan

```text
SEARCH i USING PRIMARY KEY (ward=?)
SEARCH r USING INTEGER PRIMARY KEY (rowid=?)
```
