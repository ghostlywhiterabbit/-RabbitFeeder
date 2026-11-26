"""Aircraft identification providers for RabbitFeeder."""

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AircraftLookupError(Exception):
    """Base exception for aircraft lookup failures."""


class AircraftNotFoundError(AircraftLookupError):
    """Raised when a provider has no record for an aircraft."""


class AircraftProvider:
    """Base interface for aircraft identification providers."""

    name = "base"

    def lookup(self, icao):
        raise NotImplementedError


class HexDBProvider(AircraftProvider):
    """Aircraft identification provider using the HexDB API v2."""

    name = "hexdb"
    BASE_URL = "https://hexdb.io/api/v2/aircraft/"
    TIMEOUT = 10

    def lookup(self, icao):
        """Look up an aircraft and return RabbitFeeder-compatible fields."""
        icao = str(icao).strip().upper()

        if not re.fullmatch(r"[0-9A-F]{6}", icao):
            raise ValueError("ICAO address must contain exactly six hexadecimal characters")

        request = Request(
            self.BASE_URL + icao,
            headers={
                "Accept": "application/json",
                "User-Agent": "RabbitFeeder/1.0",
            },
        )

        try:
            with urlopen(request, timeout=self.TIMEOUT) as response:
                data = json.loads(response.read().decode("utf-8"))

        except HTTPError as error:
            if error.code == 404:
                raise AircraftNotFoundError(
                    f"No HexDB aircraft record found for {icao}"
                ) from error
            raise AircraftLookupError(
                f"HexDB returned HTTP {error.code}"
            ) from error

        except (URLError, TimeoutError, OSError) as error:
            raise AircraftLookupError(
                f"Could not contact HexDB: {error}"
            ) from error

        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise AircraftLookupError(
                "HexDB returned an invalid response"
            ) from error

        if not isinstance(data, dict):
            raise AircraftLookupError("HexDB returned an unexpected response format")

        if data.get("hex", "").upper() != icao:
            raise AircraftLookupError("HexDB response ICAO address did not match the request")

        return {
            "icao": icao,
            "registration": data.get("registration"),
            "manufacturer": data.get("manufacturer"),
            "model": data.get("type"),
            "icao_type": data.get("icao_type_code"),
            "registered_owner": data.get("registered_owner"),
            "operator_flag_code": data.get("operator_flag_code"),
            "images": data.get("images"),
            "source": self.name,
        }


from datetime import datetime, timedelta, timezone


class AircraftLookupService:
    """Coordinates aircraft providers and local database caching."""

    CACHE_PERIODS = {
        "found": timedelta(days=30),
        "not_found": timedelta(days=7),
        "error": timedelta(minutes=5),
        "pending": timedelta(minutes=2),
    }

    def __init__(self, database, providers=None):
        self.database = database
        self.providers = providers or [HexDBProvider()]

    def _cache_is_valid(self, aircraft):
        """Check whether a previous lookup result is still reusable."""
        if not aircraft:
            return False

        status = aircraft.get("lookup_status")
        last_lookup = aircraft.get("last_lookup")

        if not status or not last_lookup:
            return False

        cache_period = self.CACHE_PERIODS.get(status)

        if not cache_period:
            return False

        try:
            checked_at = datetime.fromisoformat(last_lookup)
        except (TypeError, ValueError):
            return False

        return datetime.now(timezone.utc).replace(tzinfo=None) - checked_at < cache_period

    def lookup(self, icao, force=False):
        """Return cached aircraft data or retrieve fresh provider data."""
        icao = str(icao).strip().upper()

        if not re.fullmatch(r"[0-9A-F]{6}", icao):
            raise ValueError("ICAO address must contain six hexadecimal characters")

        cached = self.database.get_aircraft(icao)

        if not force and self._cache_is_valid(cached):
            if cached["lookup_status"] == "not_found":
                return None
            return cached

        if not cached:
            self.database.save_aircraft({"icao": icao})

        self.database.update_lookup_status(icao, "pending")

        provider_errors = []

        for provider in self.providers:
            try:
                result = provider.lookup(icao)
                self.database.save_aircraft(result)
                self.database.update_lookup_status(icao, "found")
                return self.database.get_aircraft(icao)

            except AircraftNotFoundError:
                continue

            except AircraftLookupError as error:
                provider_errors.append(str(error))
                continue

            except Exception:
                self.database.update_lookup_status(icao, "error")
                raise

        if provider_errors:
            self.database.update_lookup_status(icao, "error")
            return self.database.get_aircraft(icao)

        self.database.update_lookup_status(icao, "not_found")
        return None
