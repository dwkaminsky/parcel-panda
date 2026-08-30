import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { datasets, getDataset, statusLabels } from "../catalog";

export function generateStaticParams() {
  return datasets.map((dataset) => ({ slug: dataset.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const dataset = getDataset(slug);
  if (!dataset) return {};
  return { title: `${dataset.name} · Parcel Panda`, description: dataset.description };
}

export default async function DatasetDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const dataset = getDataset(slug);
  if (!dataset) notFound();

  return (
    <main className="catalog-shell detail-shell">
      <div className="catalog-wrap detail-wrap">
        <header className="site-header">
          <Link href="/" className="brand" aria-label="Parcel Panda home"><span>🐼</span><strong>Parcel Panda</strong></Link>
          <nav aria-label="Primary navigation"><Link href="/">Properties</Link><Link className="active" href="/data">Data catalog</Link></nav>
          <span className="location-pill">North Carolina</span>
        </header>

        <Link href="/data" className="back-link"><span aria-hidden="true">←</span> All datasets</Link>

        <article>
          <header className="detail-hero">
            <div className="detail-icon" aria-hidden="true">{dataset.icon}</div>
            <div className="detail-title">
              <p className="dataset-category">{dataset.category}</p>
              <h1>{dataset.name}</h1>
              <p>{dataset.description}</p>
              <div className="detail-badges"><span className={`status status-${dataset.status}`}>{statusLabels[dataset.status]}</span><span>{dataset.geography}</span></div>
            </div>
            <dl className="detail-summary">
              <div><dt>Coverage</dt><dd>{dataset.coverage}</dd></div>
              <div><dt>Update rhythm</dt><dd>{dataset.cadence}</dd></div>
              <div><dt>Sources</dt><dd>{dataset.sources.length}</dd></div>
            </dl>
          </header>

          <div className="detail-grid">
            <div className="detail-main">
              <section className="detail-section">
                <p className="eyebrow">What’s in the box</p><h2>Fields we expect to make useful</h2>
                <ul className="field-list">{dataset.fields.map((field) => <li key={field}><span aria-hidden="true">✓</span>{field}</li>)}</ul>
              </section>

              <section className="detail-section">
                <p className="eyebrow">Source registry</p><h2>Where this data comes from</h2>
                <div className="source-list">
                  {dataset.sources.map((source) => (
                    <article className="source-card" key={source.name}>
                      <div><span className={`access access-${source.access.toLowerCase()}`}>{source.access}</span><span>{source.geography}</span></div>
                      <h3>{source.name}</h3><p className="source-publisher">{source.publisher}</p><p>{source.note}</p>
                      <a href={source.url} target={source.url.startsWith("http") ? "_blank" : undefined} rel={source.url.startsWith("http") ? "noreferrer" : undefined}>View original source <span aria-hidden="true">↗</span></a>
                    </article>
                  ))}
                </div>
              </section>
            </div>

            <aside className="detail-aside">
              <section><p className="eyebrow">Read this first</p><h2>Known limitations</h2><p>{dataset.limitations}</p></section>
              <section><p className="eyebrow">Under the hood</p><h2>Technical notes</h2><p>{dataset.technicalNote}</p></section>
            </aside>
          </div>
        </article>

        <footer className="catalog-footer"><p>Parcel Panda · Property intelligence with a softer footprint.</p><Link href="/data">Keep exploring data →</Link></footer>
      </div>
    </main>
  );
}
