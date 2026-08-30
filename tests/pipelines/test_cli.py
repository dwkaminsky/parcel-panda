from __future__ import annotations

import unittest

from pipelines.__main__ import build_parser, options_from_args, parse_options
from pipelines.config import DEFAULT_DATASETS, DatasetId


class PipelineCliParserTests(unittest.TestCase):
    def test_defaults_are_safe_and_bounded(self) -> None:
        options = parse_options([])

        self.assertEqual(options.datasets, DEFAULT_DATASETS)
        self.assertTrue(options.dry_run)
        self.assertEqual(options.limit, 500)
        self.assertTrue(options.include_raw_payloads)
        self.assertIsNone(options.county_fips)

    def test_explicit_write_and_source_controls(self) -> None:
        options = parse_options(
            [
                "--dataset",
                "parcel-records",
                "--dataset",
                "housing-demographics",
                "--county-fips",
                "183",
                "--limit",
                "25",
                "--no-raw-payloads",
                "--write",
            ]
        )

        self.assertEqual(
            options.datasets,
            (DatasetId.PARCEL_RECORDS, DatasetId.HOUSING_DEMOGRAPHICS),
        )
        self.assertFalse(options.dry_run)
        self.assertEqual(options.county_fips, "37183")
        self.assertEqual(options.limit, 25)
        self.assertFalse(options.include_raw_payloads)

    def test_invalid_dataset_is_rejected_by_argparse(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            parse_options(["--dataset", "not-a-dataset"])

        self.assertEqual(raised.exception.code, 2)

    def test_invalid_county_is_rejected(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--county-fips", "99999"])

        with self.assertRaisesRegex(ValueError, "North Carolina county FIPS"):
            options_from_args(args)

    def test_limit_must_stay_within_run_options_bounds(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--limit", "5001"])

        with self.assertRaises(ValueError):
            options_from_args(args)


if __name__ == "__main__":
    unittest.main()
