import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


load_dotenv(".env.local")


url = os.environ["DATABASE_URL_DIRECT"].replace(
    "postgresql://",
    "postgresql+psycopg://",
    1,
)

engine = create_engine(url)


with engine.begin() as conn:
    conn.execute(
        text(
            """
            INSERT INTO properties (
                parcel_id,
                address,
                city,
                state,
                zip_code,
                latitude,
                longitude,
                assessed_value,
                source,
                updated_at
            )
            VALUES (
                :parcel_id,
                :address,
                :city,
                :state,
                :zip_code,
                :latitude,
                :longitude,
                :assessed_value,
                :source,
                NOW()
            )
            ON CONFLICT (parcel_id)
            DO UPDATE SET
                assessed_value = EXCLUDED.assessed_value,
                updated_at = NOW()
            """
        ),
        {
            "parcel_id": "TEST-0001",
            "address": "123 Test Street",
            "city": "Raleigh",
            "state": "NC",
            "zip_code": "27601",
            "latitude": 35.7796,
            "longitude": -78.6382,
            "assessed_value": 475000,
            "source": "test",
        },
    )


print("Pipeline complete")
