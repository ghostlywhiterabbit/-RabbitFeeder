"""Local SQLite database for aircraft identification and enrichment."""

import json
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "aircraft.db"


class AircraftDatabase:
    """Stores aircraft identification data locally."""

    def __init__(self, database_path=DEFAULT_DATABASE):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialise(self):
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS aircraft (
                    icao TEXT PRIMARY KEY,
                    registration TEXT,
                    manufacturer TEXT,
                    model TEXT,
                    icao_type TEXT,
                    operator TEXT,
                    registered_owner TEXT,
                    operator_flag_code TEXT,
                    images TEXT,
                    country TEXT,
                    serial_number TEXT,
                    category TEXT,
                    source TEXT,
                    first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            existing = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(aircraft)")
            }

            for column in (
                "registered_owner",
                "operator_flag_code",
                "images",
                "lookup_status",
                "last_lookup",
            ):
                if column not in existing:
                    connection.execute(
                        f"ALTER TABLE aircraft ADD COLUMN {column} TEXT"
                    )

            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_aircraft_registration
                ON aircraft(registration)
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_aircraft_operator
                ON aircraft(operator)
            """)

    def get_aircraft(self, icao):
        """Return one aircraft record, or None if it is not cached."""
        if not icao:
            return None

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM aircraft WHERE icao = ?",
                (icao.strip().upper(),)
            ).fetchone()

        return dict(row) if row else None

    def save_aircraft(self, aircraft):
        """Insert or update an aircraft without erasing existing details."""
        icao = str(aircraft.get("icao", "")).strip().upper()

        if not icao:
            raise ValueError("An ICAO address is required")

        fields = (
            "registration",
            "manufacturer",
            "model",
            "icao_type",
            "operator",
            "registered_owner",
            "operator_flag_code",
            "images",
            "country",
            "serial_number",
            "category",
            "source",
        )

        values = []

        for field in fields:
            value = aircraft.get(field)

            if field == "images" and value is not None:
                if not isinstance(value, str):
                    value = json.dumps(value)

            values.append(
                str(value).strip() or None if value is not None else None
            )

        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)

        updates = ", ".join(
            f"{field} = COALESCE(excluded.{field}, aircraft.{field})"
            for field in fields
        )

        query = f"""
            INSERT INTO aircraft (icao, {columns})
            VALUES (?, {placeholders})
            ON CONFLICT(icao) DO UPDATE SET
                {updates},
                updated_at = CURRENT_TIMESTAMP
        """

        with self._connect() as connection:
            connection.execute(query, [icao, *values])

        return self.get_aircraft(icao)

    def search_aircraft(self, search_term, limit=50):
        """Search cached aircraft by ICAO, registration, model or operator."""
        term = f"%{search_term.strip()}%"

        with self._connect() as connection:
            rows = connection.execute("""
                SELECT * FROM aircraft
                WHERE icao LIKE ?
                   OR registration LIKE ?
                   OR manufacturer LIKE ?
                   OR model LIKE ?
                   OR operator LIKE ?
                   OR registered_owner LIKE ?
                ORDER BY registration, icao
                LIMIT ?
            """, (term, term, term, term, term, term, limit)).fetchall()

        return [dict(row) for row in rows]

    def update_lookup_status(self, icao, status):
        """Record the result and time of an aircraft lookup."""
        if not icao:
            raise ValueError("An ICAO address is required")

        allowed_statuses = {"pending", "found", "not_found", "error"}

        if status not in allowed_statuses:
            raise ValueError(f"Invalid lookup status: {status}")

        with self._connect() as connection:
            connection.execute("""
                UPDATE aircraft
                SET lookup_status = ?,
                    last_lookup = CURRENT_TIMESTAMP
                WHERE icao = ?
            """, (status, icao.strip().upper()))
