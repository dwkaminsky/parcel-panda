export type DatasetStatus = "available" | "partial" | "in-development" | "planned" | "identified";
export type AccessType = "Public" | "Licensed";

export type DatasetSource = {
  name: string;
  publisher: string;
  url: string;
  geography: string;
  access: AccessType;
  note: string;
};

export type Dataset = {
  slug: string;
  name: string;
  shortName: string;
  description: string;
  category: string;
  icon: string;
  status: DatasetStatus;
  geography: string;
  coverage: string;
  cadence: string;
  fields: string[];
  sources: DatasetSource[];
  limitations: string;
  technicalNote: string;
};

export const statusLabels: Record<DatasetStatus, string> = {
  available: "Available now",
  partial: "Partial coverage",
  "in-development": "In development",
  planned: "Planned",
  identified: "Source identified",
};

export const datasets: Dataset[] = [
  {
    slug: "parcel-records",
    name: "Parcel records & assessed values",
    shortName: "Parcel records",
    description: "Searchable parcel identifiers, addresses, and assessed values—the foundation for connecting property data across sources.",
    category: "Parcels & ownership",
    icon: "⌗",
    status: "partial",
    geography: "County",
    coverage: "Raleigh demo records",
    cadence: "Demo data only",
    fields: ["Parcel ID", "Street address", "City and ZIP", "Assessed value"],
    sources: [
      {
        name: "Parcel Panda demonstration dataset",
        publisher: "Parcel Panda",
        url: "/",
        geography: "Raleigh, NC",
        access: "Public",
        note: "The current application contains demonstration records, not a production county feed.",
      },
      {
        name: "NC OneMap Parcels",
        publisher: "NC Geographic Information Coordinating Council",
        url: "https://services.nconemap.gov/secure/rest/services/NC1Map_Parcels/MapServer/0",
        geography: "All 100 NC counties",
        access: "Public",
        note: "Identified statewide source for standardized parcel geometry and core cadastral attributes.",
      },
    ],
    limitations: "Only demonstration records are currently viewable. Official county ingestion, freshness checks, and field-level provenance are not yet implemented.",
    technicalNote: "The existing FastAPI endpoint reads normalized property records from Neon Postgres. A production pipeline can preserve source identifiers and observation timestamps while normalizing county schemas.",
  },
  {
    slug: "ownership-boundaries",
    name: "Ownership & parcel boundaries",
    shortName: "Ownership & boundaries",
    description: "Parcel polygons, owner names, mailing addresses, acreage, and the spatial footprint of each property.",
    category: "Parcels & ownership",
    icon: "◇",
    status: "identified",
    geography: "Statewide",
    coverage: "Source covers 100 counties",
    cadence: "Varies by county",
    fields: ["Parcel geometry", "Owner name", "Mailing address", "Acreage"],
    sources: [
      {
        name: "NC OneMap Parcels",
        publisher: "NC Geographic Information Coordinating Council",
        url: "https://services.nconemap.gov/secure/rest/services/NC1Map_Parcels/MapServer/0",
        geography: "All 100 NC counties",
        access: "Public",
        note: "Aggregates standardized records supplied by county data producers and the Eastern Band of Cherokee Indians.",
      },
    ],
    limitations: "Coverage is statewide, but source currency and attribute completeness can differ by county. Parcel records are not surveys or legal boundary determinations.",
    technicalNote: "This integration will require geospatial ingestion, county-aware update tracking, geometry validation, and a source-record lineage table.",
  },
  {
    slug: "property-tax",
    name: "Tax assessed values & property tax",
    shortName: "Assessed values & taxes",
    description: "Tax-assessed property values, county and municipal tax rates, revaluation schedules, and valuation context across North Carolina.",
    category: "Values & taxes",
    icon: "$",
    status: "planned",
    geography: "Statewide",
    coverage: "County and municipal summaries",
    cadence: "Fiscal year",
    fields: ["Assessed value", "Tax rate", "Revaluation year", "Jurisdiction"],
    sources: [
      {
        name: "Property Tax Reports and Statistics",
        publisher: "North Carolina Department of Revenue",
        url: "https://www.ncdor.gov/taxes-forms/property-tax",
        geography: "North Carolina",
        access: "Public",
        note: "Official state hub for county tax rates, reappraisal information, and valuation reports.",
      },
    ],
    limitations: "State reports provide jurisdiction-level valuation context; parcel-level assessed values, bills, and payment status generally require separate county sources.",
    technicalNote: "The catalog keeps parcel-level assessments separate from jurisdiction-level tax rates and valuation summaries so values with different grains are not silently combined.",
  },
  {
    slug: "mortgage-balances-delinquencies",
    name: "Mortgage balances & delinquencies",
    shortName: "Mortgage health",
    description: "Regional mortgage debt balances and early- and serious-delinquency trends for understanding housing-market financial health.",
    category: "Financing & mortgages",
    icon: "%",
    status: "identified",
    geography: "County & state",
    coverage: "NC counties with sufficient samples",
    cadence: "Monthly and quarterly",
    fields: ["Mortgage balance", "Balance per capita", "30–89 day delinquency", "90+ day delinquency"],
    sources: [
      {
        name: "Mortgage Performance Trends",
        publisher: "Consumer Financial Protection Bureau",
        url: "https://www.consumerfinance.gov/data-research/mortgage-performance-trends/download-the-data/",
        geography: "State, metro, non-metro, and qualifying counties",
        access: "Public",
        note: "County-level delinquency rates from the National Mortgage Database, published only where the sample includes at least 1,000 mortgages.",
      },
      {
        name: "Household Debt and Credit Data Bank",
        publisher: "Federal Reserve Bank of New York",
        url: "https://www.newyorkfed.org/microeconomics/databank.html",
        geography: "State and selected county-level series",
        access: "Public",
        note: "Public aggregate series include mortgage debt balances, delinquency status, and related household-credit measures.",
      },
    ],
    limitations: "These are sampled, aggregated indicators—not the balance or payment status of a particular property or borrower. Counties with insufficient samples are suppressed, and source geographies differ by metric.",
    technicalNote: "Mortgage measures will be modeled as time-series observations keyed by metric, period, geography, source, and sample caveat. They will not be joined to individual parcel or owner records.",
  },
  {
    slug: "active-sale-listings",
    name: "Active for-sale listings",
    shortName: "For-sale listings",
    description: "Current asking prices, listing status, property characteristics, and days on market for homes offered for sale.",
    category: "Sales & listings",
    icon: "↗",
    status: "planned",
    geography: "Statewide",
    coverage: "Provider offers nationwide coverage",
    cadence: "Provider updates",
    fields: ["List price", "Listing status", "Days on market", "Beds and baths"],
    sources: [
      {
        name: "Property Listings API",
        publisher: "RentCast",
        url: "https://developers.rentcast.io/reference/property-listings",
        geography: "United States, filtered to NC",
        access: "Licensed",
        note: "A planned provider already used in a related local prototype for active sale and rental collection.",
      },
    ],
    limitations: "Coverage, reuse, display, and retention are subject to provider terms. This feed is not currently connected to Parcel Panda.",
    technicalNote: "The planned collector will retain observation history instead of overwriting prior listing states, enabling freshness and price-change analysis.",
  },
  {
    slug: "active-rental-listings",
    name: "Active rental listings",
    shortName: "Rental listings",
    description: "Asking rents and characteristics for active long-term rentals, supporting market context and comparable-property research.",
    category: "Sales & listings",
    icon: "⌂",
    status: "planned",
    geography: "Statewide",
    coverage: "Provider offers nationwide coverage",
    cadence: "Provider updates",
    fields: ["Asking rent", "Listing status", "Square footage", "Listed date"],
    sources: [
      {
        name: "Long-term Rental Listings API",
        publisher: "RentCast",
        url: "https://developers.rentcast.io/reference/rental-listings-long-term",
        geography: "United States, filtered to NC",
        access: "Licensed",
        note: "Supports geographic and address-based searches for active and inactive long-term rental listings.",
      },
    ],
    limitations: "Listings represent asking rent rather than executed leases. Coverage and display are governed by provider terms.",
    technicalNote: "Normalized listing observations will be kept distinct from modeled rent estimates and Census neighborhood benchmarks.",
  },
  {
    slug: "housing-demographics",
    name: "Housing & neighborhood context",
    shortName: "Neighborhood context",
    description: "Housing tenure, vacancy, rent, home value, income, and other community estimates at consistent Census geographies.",
    category: "Neighborhood context",
    icon: "▦",
    status: "identified",
    geography: "Census geography",
    coverage: "Statewide tracts and block groups",
    cadence: "Annual estimates",
    fields: ["Median gross rent", "Median home value", "Vacancy", "Renter share"],
    sources: [
      {
        name: "American Community Survey 5-Year Data API",
        publisher: "U.S. Census Bureau",
        url: "https://www.census.gov/programs-surveys/acs/data/data-via-api.html",
        geography: "NC counties, tracts, and block groups",
        access: "Public",
        note: "Annual statistical estimates with margins of error; not property-level observations.",
      },
    ],
    limitations: "ACS values are survey estimates for areas and periods, not measurements of a particular parcel. Margins of error must remain visible.",
    technicalNote: "The future model will store estimate, margin of error, vintage, table, variable, and Census geography together to prevent misleading comparisons.",
  },
  {
    slug: "flood-hazards",
    name: "Flood hazards & elevation",
    shortName: "Flood & elevation",
    description: "Mapped flood hazards, elevation models, and building footprints for understanding a property’s physical context.",
    category: "Hazards & environment",
    icon: "≈",
    status: "identified",
    geography: "Statewide",
    coverage: "State spatial downloads",
    cadence: "Source-specific",
    fields: ["Flood hazard area", "Elevation", "Building footprint", "Map vintage"],
    sources: [
      {
        name: "NC Emergency Management Spatial Data Download",
        publisher: "North Carolina Emergency Management",
        url: "https://assets.nconemap.gov/pages/hub/sdd/index.html",
        geography: "North Carolina",
        access: "Public",
        note: "Official download hub for flood hazards, LiDAR, elevation models, and building footprints.",
      },
    ],
    limitations: "Mapped layers differ in vintage and intended use. Catalog results should never substitute for an official flood determination or site survey.",
    technicalNote: "Raster, vector, and parcel datasets need explicit vintages and spatial reference metadata before they can be joined reproducibly.",
  },
  {
    slug: "zoning-land-use",
    name: "Zoning & future land use",
    shortName: "Zoning & land use",
    description: "Local zoning districts, overlays, and adopted future land-use designations that shape what may be built where.",
    category: "Development & land use",
    icon: "▤",
    status: "identified",
    geography: "Municipal",
    coverage: "Varies by local government",
    cadence: "Varies by jurisdiction",
    fields: ["Zoning district", "Overlay", "Jurisdiction", "Ordinance reference"],
    sources: [
      {
        name: "Local planning and GIS authorities",
        publisher: "North Carolina municipalities and counties",
        url: "https://www.nconemap.gov/",
        geography: "Municipal and county jurisdictions",
        access: "Public",
        note: "No single normalized statewide zoning source has been selected; sources must be cataloged jurisdiction by jurisdiction.",
      },
    ],
    limitations: "Zoning data is fragmented, changes locally, and may not reflect site-specific approvals. The applicable planning authority remains definitive.",
    technicalNote: "A canonical zoning model should preserve the source district code and ordinance link rather than pretending local classifications are interchangeable.",
  },
];

export const categories = Array.from(new Set(datasets.map((dataset) => dataset.category)));

export function getDataset(slug: string) {
  return datasets.find((dataset) => dataset.slug === slug);
}
