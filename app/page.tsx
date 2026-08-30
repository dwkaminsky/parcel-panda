"use client";

import { useEffect, useState } from "react";

type Property = {
  id: number;
  parcel_id: string;
  address: string | null;
  city: string | null;
  state: string | null;
  assessed_value: number | null;
};

export default function Home() {
  const [properties, setProperties] = useState<Property[]>([]);

  useEffect(() => {
    fetch("/api/properties")
      .then((response) => response.json())
      .then(setProperties);
  }, []);

  return (
    <main className="p-8">
      <h1 className="text-3xl font-bold">Plot Twist</h1>

      {properties.map((property) => (
        <div key={property.id} className="mt-4">
          <div>{property.address}</div>
          <div>${Number(property.assessed_value).toLocaleString()}</div>
        </div>
      ))}
    </main>
  );
}
