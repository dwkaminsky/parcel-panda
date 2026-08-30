import type { Metadata } from "next";
import Link from "next/link";
import CatalogClient from "./catalog-client";
import { datasets } from "./catalog";

export const metadata: Metadata = {
  title: "Property Data Catalog · Parcel Panda",
  description: "Explore the public and licensed North Carolina property data available now and planned for Parcel Panda.",
};

export default function DataCatalogPage() {
  const available = datasets.filter((dataset) => dataset.status === "available" || dataset.status === "partial").length;
  const publicSources = datasets.flatMap((dataset) => dataset.sources).filter((source) => source.access === "Public").length;

  return (
    <main className="catalog-shell">
      <div className="catalog-wrap">
        <header className="site-header">
          <Link href="/" className="brand" aria-label="Parcel Panda home"><span>🐼</span><strong>Parcel Panda</strong></Link>
          <nav aria-label="Primary navigation"><Link href="/">Properties</Link><Link className="active" href="/data">Data catalog</Link></nav>
          <span className="location-pill">North Carolina</span>
        </header>

        <section className="catalog-intro">
          <div>
            <p className="eyebrow"><span aria-hidden="true">✦</span> Property Data Catalog</p>
            <h1>See what’s inside<br /><em>every parcel.</em></h1>
            <p className="catalog-lede">A transparent guide to the North Carolina property data you can explore today—and the sources we’re carefully connecting next.</p>
          </div>
          <dl className="catalog-stats" aria-label="Catalog summary">
            <div><dt>{datasets.length}</dt><dd>datasets cataloged</dd></div>
            <div><dt>{available}</dt><dd>available now</dd></div>
            <div><dt>{publicSources}</dt><dd>public source records</dd></div>
          </dl>
        </section>

        <section aria-labelledby="browse-heading" className="browse-section">
          <div className="section-heading"><div><p className="eyebrow">Browse the shelves</p><h2 id="browse-heading">Find data by what you want to know.</h2></div><p>Every card is honest about coverage, access, and readiness.</p></div>
          <CatalogClient />
        </section>

        <footer className="catalog-footer"><p>Parcel Panda · Property intelligence with a softer footprint.</p><p>Sources cited individually · Coverage stated plainly</p></footer>
      </div>
    </main>
  );
}
