import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.index_table_experiment import (
    TARGET_WARD,
    baseline_query,
    benchmark,
    create_database,
    indexed_query,
    open_database,
    query_plan,
)


class IndexTableExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        test_temp_root = Path.cwd() / ".test-tmp"
        test_temp_root.mkdir(exist_ok=True)
        cls.temp_dir = tempfile.TemporaryDirectory(dir=test_temp_root)
        cls.db_path = Path(cls.temp_dir.name) / "test.db"
        create_database(cls.db_path, record_count=1_000, seed=20261026)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_generates_exact_record_and_index_counts(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            residents = connection.execute("SELECT COUNT(*) FROM residents").fetchone()[0]
            index_rows = connection.execute("SELECT COUNT(*) FROM ward_index").fetchone()[0]
        self.assertEqual(1_000, residents)
        self.assertEqual(residents, index_rows)

    def test_address_uses_required_three_part_shape(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            addresses = connection.execute("SELECT permanent_address FROM residents").fetchall()
        for (raw_address,) in addresses:
            address = json.loads(raw_address)
            self.assertEqual(3, len(address))
            self.assertTrue(all(isinstance(part, str) and part for part in address))

    def test_baseline_and_index_table_are_equivalent(self) -> None:
        with open_database(self.db_path) as connection:
            baseline = baseline_query(connection, TARGET_WARD)
            indexed = indexed_query(connection, TARGET_WARD)
        self.assertGreater(len(baseline), 0)
        self.assertEqual([row.id for row in baseline], [row.id for row in indexed])

    def test_target_ward_occurs_in_multiple_provinces(self) -> None:
        with open_database(self.db_path) as connection:
            residents = baseline_query(connection, TARGET_WARD)
        self.assertGreater(len({resident.province for resident in residents}), 1)

    def test_query_plan_uses_index_table_primary_key(self) -> None:
        with open_database(self.db_path) as connection:
            plan = " ".join(query_plan(connection, TARGET_WARD)).upper()
        self.assertIn("SEARCH I USING PRIMARY KEY", plan)

    def test_benchmark_verifies_equivalent_results(self) -> None:
        result = benchmark(self.db_path, TARGET_WARD, iterations=3)
        self.assertTrue(result["equivalent_results"])
        self.assertEqual(1_000, result["records"])
        self.assertEqual(1_000, result["index_rows"])


if __name__ == "__main__":
    unittest.main()
