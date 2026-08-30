"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type Property = {
  id: number;
  parcel_id: string;
  address: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  assessed_value: number | string | null;
};

function formatCurrency(value: Property["assessed_value"]) {
  if (value === null) {
    return "Not assessed";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

export default function Home() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadProperties() {
      try {
        const response = await fetch("/api/properties", {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error("We couldn’t fetch the parcel list.");
        }

        setProperties(await response.json());
      } catch (loadError) {
        if (loadError instanceof Error && loadError.name !== "AbortError") {
          setError(loadError.message);
        }
      } finally {
        setIsLoading(false);
      }
    }

    loadProperties();
    return () => controller.abort();
  }, []);

  return (
    <main className="min-h-screen overflow-hidden px-5 pb-16 sm:px-8">
      <div className="mx-auto max-w-6xl">
        <header className="flex items-center justify-between py-6 sm:py-8">
          <a href="#top" className="flex items-center gap-3" aria-label="Parcel Panda home">
            <span className="grid size-11 place-items-center rounded-2xl bg-[var(--forest)] text-2xl shadow-[0_5px_0_var(--forest-dark)]">
              🐼
            </span>
            <span className="text-xl font-bold tracking-[-0.03em] text-[var(--ink)]">
              Parcel Panda
            </span>
          </a>
          <div className="flex items-center gap-2">
            <Link href="/data" className="rounded-full border border-[var(--forest)] bg-[var(--forest)] px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-[var(--forest-dark)]">Data catalog</Link>
            <span className="hidden rounded-full border border-[var(--line)] bg-white/70 px-3 py-1.5 text-xs font-semibold text-[var(--muted)] shadow-sm backdrop-blur sm:inline">Raleigh, NC</span>
          </div>
        </header>

        <section id="top" className="relative py-14 sm:py-24">
          <div className="max-w-3xl">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full bg-[var(--mango-soft)] px-3 py-1.5 text-sm font-semibold text-[var(--mango-dark)]">
              <span aria-hidden="true">📦</span>
              Property data, neatly delivered
            </div>
            <h1 className="text-balance text-5xl font-bold leading-[0.98] tracking-[-0.055em] text-[var(--ink)] sm:text-7xl">
              Every parcel has a story.
              <span className="block text-[var(--forest)]">Let’s unpack it.</span>
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-[var(--muted)] sm:text-xl">
              Friendly real-estate intelligence for exploring property records,
              values, and the places behind every parcel.
            </p>
          </div>
          <div
            aria-hidden="true"
            className="absolute -right-8 top-10 hidden rotate-6 rounded-[2.5rem] border border-[var(--line)] bg-white/75 p-8 text-7xl shadow-[0_24px_80px_rgba(31,70,58,0.12)] backdrop-blur lg:block"
          >
            🐼📦
          </div>
        </section>

        <section aria-labelledby="properties-heading">
          <div className="mb-6 flex items-end justify-between gap-4 border-b border-[var(--line)] pb-5">
            <div>
              <p className="mb-1 text-sm font-semibold uppercase tracking-[0.16em] text-[var(--forest)]">
                Parcel feed
              </p>
              <h2 id="properties-heading" className="text-3xl font-bold tracking-[-0.04em] text-[var(--ink)]">
                Properties on the map
              </h2>
            </div>
            {!isLoading && !error ? (
              <span className="shrink-0 text-sm font-medium text-[var(--muted)]">
                {properties.length} {properties.length === 1 ? "property" : "properties"}
              </span>
            ) : null}
          </div>

          {isLoading ? (
            <div className="rounded-3xl border border-[var(--line)] bg-white/70 p-8 text-[var(--muted)] shadow-sm">
              Panda is fetching the parcels…
            </div>
          ) : null}

          {error ? (
            <div className="rounded-3xl border border-red-200 bg-red-50 p-8 text-red-800 shadow-sm">
              {error} Please try again in a moment.
            </div>
          ) : null}

          {!isLoading && !error && properties.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-[var(--line)] bg-white/50 p-10 text-center text-[var(--muted)]">
              No parcels have arrived yet.
            </div>
          ) : null}

          <div className="grid gap-5 md:grid-cols-2">
            {properties.map((property) => (
              <article
                key={property.id}
                className="group rounded-3xl border border-[var(--line)] bg-white/80 p-6 shadow-[0_14px_40px_rgba(31,70,58,0.07)] transition duration-200 hover:-translate-y-1 hover:shadow-[0_20px_50px_rgba(31,70,58,0.12)]"
              >
                <div className="mb-8 flex items-start justify-between gap-4">
                  <div className="grid size-12 shrink-0 place-items-center rounded-2xl bg-[var(--leaf-soft)] text-2xl">
                    🏡
                  </div>
                  <span className="rounded-full bg-[var(--cream)] px-3 py-1 font-mono text-xs font-medium text-[var(--muted)]">
                    {property.parcel_id}
                  </span>
                </div>
                <h3 className="text-xl font-bold tracking-[-0.025em] text-[var(--ink)]">
                  {property.address ?? "Address unavailable"}
                </h3>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  {[property.city, property.state, property.zip_code].filter(Boolean).join(", ")}
                </p>
                <div className="mt-6 border-t border-[var(--line)] pt-5">
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">
                    Assessed value
                  </p>
                  <p className="mt-1 text-2xl font-bold tracking-[-0.035em] text-[var(--forest)]">
                    {formatCurrency(property.assessed_value)}
                  </p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <footer className="mt-20 flex flex-col gap-2 border-t border-[var(--line)] py-8 text-sm text-[var(--muted)] sm:flex-row sm:items-center sm:justify-between">
          <p>Parcel Panda · Property intelligence with a softer footprint.</p>
          <p>Next.js · FastAPI · Neon</p>
        </footer>
      </div>
    </main>
  );
}
