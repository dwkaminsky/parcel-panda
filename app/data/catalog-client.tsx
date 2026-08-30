"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { categories, datasets, statusLabels, type DatasetStatus } from "./catalog";

const availabilityOptions: { label: string; value: "all" | DatasetStatus }[] = [
  { label: "All availability", value: "all" },
  { label: "Available now", value: "partial" },
  { label: "In development", value: "in-development" },
  { label: "Planned", value: "planned" },
  { label: "Source identified", value: "identified" },
];

export default function CatalogClient() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All data");
  const [geography, setGeography] = useState("All geographies");
  const [availability, setAvailability] = useState<(typeof availabilityOptions)[number]["value"]>("all");

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return datasets.filter((dataset) => {
      const searchable = [dataset.name, dataset.description, dataset.category, dataset.geography, dataset.coverage, ...dataset.fields, ...dataset.sources.map((source) => `${source.name} ${source.publisher}`)].join(" ").toLowerCase();
      return (!normalizedQuery || searchable.includes(normalizedQuery)) &&
        (category === "All data" || dataset.category === category) &&
        (geography === "All geographies" || dataset.geography === geography) &&
        (availability === "all" || dataset.status === availability);
    });
  }, [availability, category, geography, query]);

  const geographies = Array.from(new Set(datasets.map((dataset) => dataset.geography)));

  return (
    <>
      <div className="catalog-controls" aria-label="Catalog filters">
        <label className="catalog-search">
          <span className="sr-only">Search datasets and sources</span>
          <span aria-hidden="true">⌕</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search datasets, sources, or fields…" type="search" />
        </label>
        <label>
          <span className="sr-only">Filter by geography</span>
          <select value={geography} onChange={(event) => setGeography(event.target.value)}>
            <option>All geographies</option>
            {geographies.map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
        <label>
          <span className="sr-only">Filter by availability</span>
          <select value={availability} onChange={(event) => setAvailability(event.target.value as typeof availability)}>
            {availabilityOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
      </div>

      <div className="category-tabs" role="group" aria-label="Filter by data category">
        {["All data", ...categories].map((item) => (
          <button key={item} type="button" className={category === item ? "active" : ""} onClick={() => setCategory(item)}>{item}</button>
        ))}
      </div>

      <div className="catalog-result-head">
        <p><strong>{filtered.length}</strong> {filtered.length === 1 ? "dataset" : "datasets"}</p>
        <p>North Carolina catalog · proof of concept</p>
      </div>

      {filtered.length ? (
        <div className="dataset-grid">
          {filtered.map((dataset) => (
            <Link className="dataset-card" href={`/data/${dataset.slug}`} key={dataset.slug}>
              <div className="dataset-card-top">
                <span className="dataset-icon" aria-hidden="true">{dataset.icon}</span>
                <span className={`status status-${dataset.status}`}>{statusLabels[dataset.status]}</span>
              </div>
              <p className="dataset-category">{dataset.category}</p>
              <h2>{dataset.name}</h2>
              <p className="dataset-description">{dataset.description}</p>
              <div className="dataset-meta">
                <span><small>Geography</small>{dataset.geography}</span>
                <span><small>Coverage</small>{dataset.coverage}</span>
              </div>
              <div className="dataset-card-foot">
                <span>{dataset.sources.length} {dataset.sources.length === 1 ? "source" : "sources"}</span>
                <strong>View dataset <span aria-hidden="true">→</span></strong>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="catalog-empty">
          <span aria-hidden="true">🐼</span>
          <h2>No datasets wandered this way.</h2>
          <p>Try a broader search or clear one of the filters.</p>
          <button type="button" onClick={() => { setQuery(""); setCategory("All data"); setGeography("All geographies"); setAvailability("all"); }}>Clear filters</button>
        </div>
      )}
    </>
  );
}
