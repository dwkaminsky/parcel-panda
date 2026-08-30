from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from prefect.context import get_run_context

from pipelines.config import DatasetId, RunOptions
from pipelines.contracts import CatalogRunSummary, ExtractedBatch, LoadSummary
from pipelines.sources import (
    CensusACS5Adapter,
    CFPBMortgagePerformanceAdapter,
    CharlotteZoningAdapter,
    NCEMFloodAdapter,
    NCDORPropertyTaxAdapter,
    NCOneMapAssessedValueAdapter,
    NCOneMapOwnershipAdapter,
    NCOneMapParcelAdapter,
    NYFedHouseholdDebtAdapter,
    RentCastRentalAdapter,
    RentCastSaleAdapter,
)
from pipelines.sources.base import SourceAdapter
from pipelines.storage import make_repository_from_env


AdapterFactory = Callable[[], SourceAdapter]
AdapterKey = tuple[str, str]

ADAPTER_FACTORIES: dict[AdapterKey, AdapterFactory] = {
    (DatasetId.PARCEL_RECORDS, "nc-onemap-parcels"): NCOneMapParcelAdapter,
    (DatasetId.OWNERSHIP_BOUNDARIES, "nc-onemap-parcels"): NCOneMapOwnershipAdapter,
    (DatasetId.PROPERTY_TAX, "nc-onemap-parcels"): NCOneMapAssessedValueAdapter,
    (DatasetId.PROPERTY_TAX, "ncdor-property-tax"): NCDORPropertyTaxAdapter,
    (DatasetId.MORTGAGE, "cfpb-mortgage-performance"): CFPBMortgagePerformanceAdapter,
    (DatasetId.MORTGAGE, "nyfed-household-debt"): NYFedHouseholdDebtAdapter,
    (DatasetId.SALE_LISTINGS, "rentcast-sale"): RentCastSaleAdapter,
    (DatasetId.RENTAL_LISTINGS, "rentcast-rental"): RentCastRentalAdapter,
    (DatasetId.HOUSING_DEMOGRAPHICS, "census-acs5"): CensusACS5Adapter,
    (DatasetId.FLOOD_HAZARDS, "ncem-fris"): NCEMFloodAdapter,
    (DatasetId.ZONING, "charlotte-zoning"): CharlotteZoningAdapter,
}


def selected_adapter_keys(options: RunOptions) -> list[AdapterKey]:
    selected = {dataset.value for dataset in options.datasets}
    return [key for key in ADAPTER_FACTORIES if key[0] in selected]


@task(
    name="extract-source",
    retries=2,
    retry_delay_seconds=[5, 20],
    cache_policy=NO_CACHE,
    persist_result=False,
)
def extract_source(key: AdapterKey, options: RunOptions) -> ExtractedBatch:
    adapter = ADAPTER_FACTORIES[key]()
    batch = adapter.extract(options)
    if (batch.dataset_slug, batch.source_slug) != key:
        raise ValueError(
            f"Adapter {type(adapter).__name__} returned "
            f"{batch.dataset_slug}/{batch.source_slug}, expected {key[0]}/{key[1]}"
        )
    return batch


@task(
    name="load-source",
    retries=2,
    retry_delay_seconds=[2, 10],
    cache_policy=NO_CACHE,
    persist_result=False,
)
def load_source(
    batch: ExtractedBatch,
    options: RunOptions,
    prefect_flow_run_id: UUID | None,
) -> LoadSummary:
    if options.dry_run:
        return LoadSummary(
            dataset_slug=batch.dataset_slug,
            source_slug=batch.source_slug,
            extracted=len(batch.records),
            dry_run=True,
            skipped_reason=batch.skipped_reason,
        )
    return make_repository_from_env().ingest_batch(
        batch,
        options,
        prefect_flow_run_id=prefect_flow_run_id,
    )


@flow(name="property-data-catalog", log_prints=True)
def run_catalog(options: RunOptions | dict) -> CatalogRunSummary:
    """Extract selected NC catalog sources and optionally load them idempotently."""
    validated_options = RunOptions.model_validate(options)
    context = get_run_context()
    flow_run_id = context.flow_run.id if context.flow_run else None

    extraction_futures = [
        extract_source.with_options(name=f"extract-{source_slug}").submit(
            (dataset_slug, source_slug),
            validated_options,
        )
        for dataset_slug, source_slug in selected_adapter_keys(validated_options)
    ]

    summaries: list[LoadSummary] = []
    for future in extraction_futures:
        batch = future.result()
        for warning in batch.warnings:
            print(f"{batch.source_slug}: {warning}")
        summaries.append(load_source(batch, validated_options, flow_run_id))

    return CatalogRunSummary(
        datasets_requested=len(validated_options.datasets),
        batches=summaries,
        dry_run=validated_options.dry_run,
    )
