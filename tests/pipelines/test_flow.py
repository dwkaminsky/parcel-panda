from __future__ import annotations

from pipelines.config import DatasetId, RunOptions
from pipelines.flow import ADAPTER_FACTORIES, selected_adapter_keys


def test_every_catalog_dataset_has_a_registered_adapter() -> None:
    registered = {str(dataset_slug) for dataset_slug, _ in ADAPTER_FACTORIES}
    assert registered == {dataset.value for dataset in DatasetId}


def test_dataset_selection_returns_every_source_for_dataset() -> None:
    options = RunOptions(datasets=(DatasetId.PROPERTY_TAX,), limit=1)

    assert selected_adapter_keys(options) == [
        (DatasetId.PROPERTY_TAX, "nc-onemap-parcels"),
        (DatasetId.PROPERTY_TAX, "ncdor-property-tax"),
    ]
