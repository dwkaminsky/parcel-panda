"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

const properties = [
  { id: 1, x: 38, y: 31, price: "$1.24m", address: "814 Glenwood Ave", detail: "4 bd · 3 ba · 2,810 sq ft", tone: "dark", type: "house" },
  { id: 2, x: 51, y: 44, price: "$684k", address: "328 N West Street", detail: "3 bd · 2 ba · 1,940 sq ft", tone: "light", type: "house" },
  { id: 3, x: 68, y: 27, price: "$892k", address: "1207 Mordecai Dr", detail: "8 units · 6,120 sq ft", tone: "dark", type: "multi" },
  { id: 4, x: 61, y: 62, price: "$548k", address: "719 E Hargett St", detail: "2 bd · 2 ba · 1,310 sq ft", tone: "light", type: "condo" },
  { id: 5, x: 27, y: 67, price: "$742k", address: "406 S Boylan Ave", detail: "3 bd · 3 ba · 2,050 sq ft", tone: "light", type: "house" },
  { id: 6, x: 78, y: 51, price: "$423k", address: "1820 Oakwood Ave", detail: "0.32 acre · R-10", tone: "light", type: "land" },
  { id: 7, x: 43, y: 73, price: "$616k", address: "921 Cabarrus St", detail: "12 units · 9,880 sq ft", tone: "dark", type: "multi" },
];

const neighborhoodData = {
  "Warehouse District": { value: "$642k", change: "+8.4%", properties: "1,284" },
  "Boylan Heights": { value: "$718k", change: "+6.1%", properties: "864" },
  Oakwood: { value: "$591k", change: "+9.2%", properties: "1,106" },
};

type Neighborhood = keyof typeof neighborhoodData;

function Icon({ name }: { name: "search" | "bookmark" | "locate" | "plus" | "minus" | "chevron" }) {
  const paths = {
    search: <><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></>,
    bookmark: <path d="M6 3h12v18l-6-4-6 4V3Z"/>,
    locate: <><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="8"/><path d="M12 2V0m0 24v-2M2 12H0m24 0h-2"/></>,
    plus: <path d="M12 5v14M5 12h14"/>,
    minus: <path d="M5 12h14"/>,
    chevron: <path d="m9 18 6-6-6-6"/>,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</g></svg>;
}

function PropertyIcon({ type }: { type: string }) {
  if (type === "land") return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m3 15 4-6 3 3 2-4 5 7H3Z"/></svg>;
  if (type === "multi") return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 16V4h10v12M8 7h1m2 0h1M8 10h1m2 0h1M8 13h1m2 0h1"/></svg>;
  if (type === "condo") return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M6 16V6h8v10M8 9h1m2 0h1M8 12h1m2 0h1M4 16h12"/></svg>;
  return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m3 9 7-5 7 5v7h-5v-4H8v4H3V9Z"/></svg>;
}

export default function Home() {
  const router = useRouter();
  const [selectedProperty, setSelectedProperty] = useState(2);
  const [neighborhood, setNeighborhood] = useState<Neighborhood>("Warehouse District");
  const [propertyLayer, setPropertyLayer] = useState(true);
  const [hoveredArea, setHoveredArea] = useState<Neighborhood | null>(null);
  const selected = properties.find((property) => property.id === selectedProperty)!;
  const area = neighborhoodData[neighborhood];

  return (
    <main className="atlas-shell">
      <header className="atlas-header">
        <a className="atlas-wordmark" href="#map" aria-label="Parcel Atlas home"><span className="atlas-mark"><span /></span><strong>Parcel <em>Atlas</em></strong></a>
        <nav aria-label="Primary navigation"><a className="active" href="#map">Explore</a><Link href="/data">Data</Link><a href="#saved">Saved</a></nav>
        <div className="atlas-header-actions"><button className="icon-button" aria-label="Saved properties"><Icon name="bookmark" /></button><button className="atlas-avatar" aria-label="Open profile">DK</button></div>
      </header>

      <section className="atlas-map" id="map" aria-label="Interactive property atlas of central Raleigh">
        <div className="map-paper" aria-hidden="true" />
        <svg className="map-art" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <path className="water" d="M-80 696c162-84 257-27 376-65 107-34 130-125 273-127 146-1 213 81 362 57 116-18 193-89 349-38v277H-80Z" />
          <g className="area-shapes"><path className="area area-one" d="M79 90 330 52l124 84-30 244-166 65-183-123Z"/><path className="area area-two" d="m454 136 260-50 102 130-63 196-167 88-162-120Z"/><path className="area area-three" d="m816 216 270-60 158 119-34 238-279 48-178-149Z"/><path className="area area-four" d="m75 322 183 123 166-65 162 120-57 202-242 12-211-136Z"/><path className="area area-five" d="m586 500 167-88 178 149-92 173-310-32Z"/></g>
          <g className="minor-roads"><path d="M-20 162 1230 603M67 714 1122 30M322 0l-35 800M1023 0 795 800M0 470l1200-95M0 290l1200 280"/><path d="M117 0 491 800M663 0 467 800M872 0l129 800M0 602l1200-241M0 94l1200 542"/></g>
          <g className="major-roads"><path d="M-40 521C204 432 335 449 506 335S826 126 1248 99"/><path d="M93-50c40 180 198 240 273 364s76 278 66 540"/><path d="M-50 232c256 86 465 35 666 99s361 194 634 218"/></g>
          <g className="blocks"><path d="m460 190 66-15 29 62-64 16Zm102 74 73-21 29 69-82 20Zm-65 25 58-13 18 48-59 18Zm191 40 66-29 26 60-58 34ZM363 473l65-25 38 55-66 31Zm111 58 72-18 26 65-76 14Zm224-22 67-34 35 56-74 37Z"/></g>
          <g className="rail"><path d="M-50 765 1170-30"/><path d="M-44 774 1176-21"/></g>
          <text x="360" y="115" className="map-label large">GLENWOOD SOUTH</text><text x="485" y="418" className="map-label hero">DOWNTOWN</text><text x="895" y="198" className="map-label large">OAKWOOD</text><text x="168" y="564" className="map-label large">BOYLAN HEIGHTS</text><text x="818" y="661" className="map-label water-label">WALNUT CREEK</text>
          <g className="street-labels"><text x="570" y="292">HILLSBOROUGH ST</text><text x="318" y="492">WESTERN BLVD</text><text x="757" y="393">NEW BERN AVE</text></g>
        </svg>
        <svg className="geography-hit-map" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice" aria-label="Neighborhood geographies">
          <path d="M79 90 330 52l124 84-30 244-166 65-183-123Z" tabIndex={0} aria-label="Boylan Heights geography" onMouseEnter={() => setHoveredArea("Boylan Heights")} onMouseLeave={() => setHoveredArea(null)} onFocus={() => setHoveredArea("Boylan Heights")} onBlur={() => setHoveredArea(null)} onClick={() => router.push("/areas/boylan-heights")}/>
          <path d="m454 136 260-50 102 130-63 196-167 88-162-120Z" tabIndex={0} aria-label="Warehouse District geography" onMouseEnter={() => setHoveredArea("Warehouse District")} onMouseLeave={() => setHoveredArea(null)} onFocus={() => setHoveredArea("Warehouse District")} onBlur={() => setHoveredArea(null)} onClick={() => router.push("/areas/warehouse-district")}/>
          <path d="m816 216 270-60 158 119-34 238-279 48-178-149Z" tabIndex={0} aria-label="Oakwood geography" onMouseEnter={() => setHoveredArea("Oakwood")} onMouseLeave={() => setHoveredArea(null)} onFocus={() => setHoveredArea("Oakwood")} onBlur={() => setHoveredArea(null)} onClick={() => router.push("/areas/oakwood")}/>
        </svg>

        {hoveredArea ? <div className={`geography-hover geography-${hoveredArea.toLowerCase().replaceAll(" ", "-")}`}><p>Neighborhood</p><strong>{hoveredArea}</strong><dl><div><dt>Median value</dt><dd>{neighborhoodData[hoveredArea].value}</dd></div><div><dt>1 year</dt><dd>{neighborhoodData[hoveredArea].change}</dd></div></dl><span>Click for full profile →</span></div> : null}

        <div className="map-topbar"><div className="atlas-search"><Icon name="search"/><input aria-label="Search places or properties" placeholder="Search an address, neighborhood, or parcel"/><kbd>⌘ K</kbd></div><div className="map-context"><span>Wake County</span><strong>Raleigh, NC</strong></div></div>

        <aside className="metric-card"><p className="micro-label">Area metric</p><button className="metric-select">Median home value <span>⌄</span></button><div className="legend-gradient"/><div className="legend-scale"><span>$280k</span><span>$550k</span><span>$1.1m+</span></div><div className="metric-divider"/><label className="layer-row"><span><i className="point-swatch"/>Properties</span><input type="checkbox" checked={propertyLayer} onChange={(event) => setPropertyLayer(event.target.checked)}/><b aria-hidden="true"/></label></aside>
        <div className="zoom-controls"><button aria-label="Zoom in"><Icon name="plus"/></button><button aria-label="Zoom out"><Icon name="minus"/></button><button aria-label="Locate me"><Icon name="locate"/></button></div>
        <div className="neighborhood-tabs" aria-label="Featured neighborhoods">{(Object.keys(neighborhoodData) as Neighborhood[]).map((name) => <button key={name} className={neighborhood === name ? "active" : ""} onClick={() => setNeighborhood(name)}>{name}</button>)}</div>

        {propertyLayer ? properties.map((property) => <button key={property.id} className={`property-dot ${selectedProperty === property.id ? "selected" : ""} ${property.tone}`} style={{ left: `${property.x}%`, top: `${property.y}%` }} onClick={() => setSelectedProperty(property.id)} aria-label={`${property.address}, ${property.type}, ${property.price}`}><PropertyIcon type={property.type}/><span>{property.price}</span></button>) : null}

        <article className="area-story"><div className="story-kicker"><span/> Neighborhood snapshot</div><h1>{neighborhood}</h1><p>Historic character, tree-lined streets, and a lively mix of homes at the edge of downtown.</p><dl><div><dt>Median value</dt><dd>{area.value}</dd></div><div><dt>1 year</dt><dd className="positive">{area.change}</dd></div><div><dt>Properties</dt><dd>{area.properties}</dd></div></dl><button>Explore neighborhood <Icon name="chevron"/></button></article>
        {propertyLayer ? <article className="property-peek"><button className="peek-close" onClick={() => setPropertyLayer(false)} aria-label="Close property card">×</button><p className="micro-label">Selected property</p><div className="peek-title"><div><h2>{selected.address}</h2><p>Raleigh, NC 27603</p></div><strong>{selected.price}</strong></div><div className="peek-detail"><span>{selected.detail}</span><button aria-label="View selected property"><Icon name="chevron"/></button></div></article> : null}
        <div className="map-credit">Prototype data · © Parcel Atlas</div>
      </section>
    </main>
  );
}
