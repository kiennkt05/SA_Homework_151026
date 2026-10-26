"""Thực nghiệm Index Table theo bài giảng Database Design Pattern.

Baseline đọc toàn bộ bảng residents rồi lọc bằng vòng lặp Python.
Phương án Index Table tra secondary key (ward) để lấy reference (resident_id),
sau đó join về fact table residents.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import statistics
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator


TARGET_WARD = "Cầu Giấy"

FAMILY_NAMES = ("Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ", "Hồ")
MIDDLE_NAMES = ("Văn", "Thị", "Minh", "Ngọc", "Đức", "Thanh", "Quang", "Thu", "Gia", "Hải")
GIVEN_NAMES = ("An", "Bình", "Chi", "Dũng", "Giang", "Hà", "Hùng", "Lan", "Linh", "Nam", "Phúc", "Trang")
STREETS = (
    "Trần Duy Hưng",
    "Xuân Thủy",
    "Nguyễn Trãi",
    "Láng Hạ",
    "Kim Mã",
    "Minh Khai",
    "Hoàng Quốc Việt",
    "Phạm Văn Đồng",
)
WARDS = (
    TARGET_WARD,
    "Dịch Vọng",
    "Mai Dịch",
    "Yên Hòa",
    "Trung Hòa",
    "Mỹ Đình",
    "Bến Nghé",
    "Hải Châu",
    "An Hải",
    "Ninh Kiều",
    "Hồng Gai",
    "Đông Vệ",
)
PROVINCES = (
    "Hà Nội",
    "Hải Phòng",
    "Đà Nẵng",
    "Thành phố Hồ Chí Minh",
    "Cần Thơ",
    "Quảng Ninh",
    "Thanh Hóa",
    "Bắc Ninh",
)


@dataclass(frozen=True)
class Resident:
    id: int
    full_name: str
    address_detail: str
    ward: str
    province: str

    @property
    def permanent_address(self) -> list[str]:
        return [self.address_detail, self.ward, self.province]


def _resident_from_row(row: sqlite3.Row) -> Resident:
    address = json.loads(row["permanent_address"])
    return Resident(
        id=row["id"],
        full_name=row["full_name"],
        address_detail=address[0],
        ward=address[1],
        province=address[2],
    )


def generate_rows(count: int, seed: int) -> Iterable[tuple[int, str, str]]:
    """Sinh dữ liệu xác định được để benchmark có thể tái lập."""
    rng = random.Random(seed)
    for resident_id in range(1, count + 1):
        full_name = f"{rng.choice(FAMILY_NAMES)} {rng.choice(MIDDLE_NAMES)} {rng.choice(GIVEN_NAMES)}"
        detail = f"Số {rng.randint(1, 999)}, đường {rng.choice(STREETS)}"
        ward = rng.choice(WARDS)
        province = rng.choice(PROVINCES)
        address = json.dumps([detail, ward, province], ensure_ascii=False)
        yield resident_id, full_name, address


def create_database(db_path: Path, record_count: int, seed: int) -> None:
    """Tạo fact table và index table dạng secondary key -> record reference."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            DROP TABLE IF EXISTS ward_index;
            DROP TABLE IF EXISTS residents;

            CREATE TABLE residents (
                id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                permanent_address TEXT NOT NULL
            );

            CREATE TABLE ward_index (
                ward TEXT NOT NULL,
                resident_id INTEGER NOT NULL,
                PRIMARY KEY (ward, resident_id),
                FOREIGN KEY (resident_id) REFERENCES residents(id)
            ) WITHOUT ROWID;
            """
        )
        connection.executemany(
            "INSERT INTO residents(id, full_name, permanent_address) VALUES (?, ?, ?)",
            generate_rows(record_count, seed),
        )

        # Index table được xây từ fact table, tương tự secondary-key table trong slide.
        rows = connection.execute("SELECT id, permanent_address FROM residents")
        index_rows = ((json.loads(address)[1], resident_id) for resident_id, address in rows)
        connection.executemany(
            "INSERT INTO ward_index(ward, resident_id) VALUES (?, ?)",
            index_rows,
        )
        connection.commit()


@contextmanager
def open_database(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def baseline_query(connection: sqlite3.Connection, ward: str) -> list[Resident]:
    """Baseline: query toàn bộ DB và lọc ward bằng vòng lặp for."""
    matches: list[Resident] = []
    for row in connection.execute("SELECT id, full_name, permanent_address FROM residents ORDER BY id"):
        resident = _resident_from_row(row)
        if resident.ward == ward:
            matches.append(resident)
    return matches


def indexed_query(connection: sqlite3.Connection, ward: str) -> list[Resident]:
    """Tra Index Table theo ward rồi lấy bản ghi từ fact table."""
    rows = connection.execute(
        """
        SELECT r.id, r.full_name, r.permanent_address
        FROM ward_index AS i
        JOIN residents AS r ON r.id = i.resident_id
        WHERE i.ward = ?
        ORDER BY r.id
        """,
        (ward,),
    )
    return [_resident_from_row(row) for row in rows]


def query_plan(connection: sqlite3.Connection, ward: str) -> list[str]:
    rows = connection.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT r.id, r.full_name, r.permanent_address
        FROM ward_index AS i
        JOIN residents AS r ON r.id = i.resident_id
        WHERE i.ward = ?
        """,
        (ward,),
    )
    return [row[3] for row in rows]


def _percentile_95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def _measure(
    query: Callable[[sqlite3.Connection, str], list[Resident]],
    connection: sqlite3.Connection,
    ward: str,
    iterations: int,
) -> tuple[dict[str, float], list[Resident]]:
    samples_ms: list[float] = []
    latest: list[Resident] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        latest = query(connection, ward)
        samples_ms.append((time.perf_counter_ns() - started) / 1_000_000)
    return (
        {
            "mean_ms": statistics.fmean(samples_ms),
            "median_ms": statistics.median(samples_ms),
            "p95_ms": _percentile_95(samples_ms),
            "min_ms": min(samples_ms),
            "max_ms": max(samples_ms),
        },
        latest,
    )


def benchmark(db_path: Path, ward: str, iterations: int) -> dict[str, object]:
    with open_database(db_path) as connection:
        # Warm-up để giảm ảnh hưởng của lần đọc file/khởi tạo đầu tiên.
        baseline_query(connection, ward)
        indexed_query(connection, ward)

        baseline_stats, baseline_rows = _measure(baseline_query, connection, ward, iterations)
        indexed_stats, indexed_rows = _measure(indexed_query, connection, ward, iterations)

        baseline_ids = [row.id for row in baseline_rows]
        indexed_ids = [row.id for row in indexed_rows]
        if baseline_ids != indexed_ids:
            raise AssertionError("Baseline và Index Table trả về tập kết quả khác nhau")

        total_rows = connection.execute("SELECT COUNT(*) FROM residents").fetchone()[0]
        index_rows = connection.execute("SELECT COUNT(*) FROM ward_index").fetchone()[0]
        plans = query_plan(connection, ward)

    speedup = baseline_stats["mean_ms"] / indexed_stats["mean_ms"]
    return {
        "database": str(db_path),
        "records": total_rows,
        "index_rows": index_rows,
        "target_ward": ward,
        "matches": len(baseline_ids),
        "iterations": iterations,
        "equivalent_results": True,
        "baseline": baseline_stats,
        "index_table": indexed_stats,
        "speedup": speedup,
        "query_plan": plans,
        "sample": [asdict(row) | {"permanent_address": row.permanent_address} for row in baseline_rows[:5]],
    }


def _format_report(result: dict[str, object]) -> str:
    baseline = result["baseline"]
    indexed = result["index_table"]
    return f"""# Kết quả thực nghiệm Index Table

- Số bản ghi fact table: **{result['records']}**
- Số bản ghi index table: **{result['index_rows']}**
- Secondary key cần tìm: **{result['target_ward']}**
- Số kết quả: **{result['matches']}**
- Số lần đo mỗi phương án: **{result['iterations']}**
- Hai phương án trả cùng kết quả: **Có**

| Phương án | Mean (ms) | Median (ms) | P95 (ms) | Min (ms) | Max (ms) |
|---|---:|---:|---:|---:|---:|
| Baseline: full scan + vòng `for` | {baseline['mean_ms']:.4f} | {baseline['median_ms']:.4f} | {baseline['p95_ms']:.4f} | {baseline['min_ms']:.4f} | {baseline['max_ms']:.4f} |
| Index Table: secondary key → reference | {indexed['mean_ms']:.4f} | {indexed['median_ms']:.4f} | {indexed['p95_ms']:.4f} | {indexed['min_ms']:.4f} | {indexed['max_ms']:.4f} |

**Index Table nhanh hơn trung bình {result['speedup']:.2f} lần.**

## Query plan

```text
{chr(10).join(result['query_plan'])}
```
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark baseline và Index Table")
    parser.add_argument("--records", type=int, default=10_000)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20261026)
    parser.add_argument("--ward", default=TARGET_WARD)
    parser.add_argument("--db", type=Path, default=Path("data/people.db"))
    parser.add_argument("--json-output", type=Path, default=Path("results/benchmark.json"))
    parser.add_argument("--report-output", type=Path, default=Path("results/RESULTS.md"))
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    if args.records <= 0 or args.iterations <= 0:
        raise SystemExit("--records và --iterations phải lớn hơn 0")

    create_database(args.db, args.records, args.seed)
    result = benchmark(args.db, args.ward, args.iterations)
    report = _format_report(result)

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report_output.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
