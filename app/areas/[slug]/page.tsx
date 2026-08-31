import Link from "next/link";
import { notFound } from "next/navigation";

const areas = {
  "warehouse-district": {
    name: "Warehouse District",
    value: "$642,000",
    change: "+8.4%",
    properties: "1,284",
    sale: "$716,400",
    rent: "$2,480",
    days: "18",
    narrative:
      "A compact, design-led district where former industrial buildings meet new residential streets. Values remain resilient, led by adaptive reuse and walkability.",
  },
  "boylan-heights": {
    name: "Boylan Heights",
    value: "$718,000",
    change: "+6.1%",
    properties: "864",
    sale: "$754,200",
    rent: "$2,710",
    days: "14",
    narrative:
      "One of Raleigh’s most distinctive historic neighborhoods, with mature tree cover, architectural character, and consistently limited inventory.",
  },
  oakwood: {
    name: "Oakwood",
    value: "$591,000",
    change: "+9.2%",
    properties: "1,106",
    sale: "$628,900",
    rent: "$2,260",
    days: "21",
    narrative:
      "A historic residential quarter with a broad mix of restored homes and smaller infill properties close to the eastern edge of downtown.",
  },
} as const;

const profileStats = [
  ["Properties", "properties"],
  ["Median sale", "sale"],
  ["Median rent", "rent"],
  ["Days on market", "days"],
] as const;

const distribution = [32, 61, 92, 76, 48, 27];

export function generateStaticParams() {
  return Object.keys(areas).map((slug) => ({ slug }));
}

export default async function AreaPage({ params }: PageProps<"/areas/[slug]">) {
  const { slug } = await params;
  const area = areas[slug as keyof typeof areas];

  if (!area) notFound();

  return (
    <main className="area-profile-shell">
      <div className="area-profile-map" aria-hidden="true">
        <div className="profile-map-shape shape-a" />
        <div className="profile-map-shape shape-b" />
        <div className="profile-map-road road-a" />
        <div className="profile-map-road road-b" />
        <span>RALEIGH</span>
      </div>
      <article className="area-profile-pane">
        <Link href="/" className="profile-back">
          ← Back to atlas
        </Link>
        <p className="profile-eyebrow">Neighborhood profile · Wake County</p>
        <h1>{area.name}</h1>
        <p className="profile-narrative">{area.narrative}</p>
        <section className="profile-hero-stat">
          <span>Median home value</span>
          <strong>{area.value}</strong>
          <em>{area.change} over 12 months</em>
        </section>
        <div className="profile-stat-grid">
          {profileStats.map(([label, key]) => (
            <div key={key}>
              <span>{label}</span>
              <strong>{area[key]}</strong>
            </div>
          ))}
        </div>
        <section className="profile-section">
          <div>
            <p className="profile-eyebrow">Value distribution</p>
            <h2>Homes cluster around $600–800k</h2>
          </div>
          <div className="profile-bars">
            {distribution.map((height) => (
              <i key={height} style={{ height: `${height}%` }} />
            ))}
          </div>
          <div className="profile-axis">
            <span>$300k</span>
            <span>$1.2m+</span>
          </div>
        </section>
        <p className="profile-footnote">
          Prototype neighborhood data · Updated August 2026
        </p>
      </article>
    </main>
  );
}
