"""Read-only adapter spike for open-source MLB data libraries.

This module intentionally delegates MLB data acquisition to optional open-source
libraries. It only provides deterministic dependency diagnostics, thin wrapper
methods, and a small normalization boundary for downstream tests/reports.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import importlib
import importlib.metadata as importlib_metadata
from typing import Any

DISCLAIMER = (
    "Historical/read-only MLB data adoption spike only. "
    "Not live predictions, not betting advice."
)


@dataclass(frozen=True)
class LibraryOption:
    provider: str
    package_name: str
    import_name: str
    purpose: str
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class AdapterDiagnostic:
    provider: str
    package_name: str
    import_name: str
    installed: bool
    importable: bool
    version: str | None
    status: str
    reason: str
    disclaimer: str = DISCLAIMER


class AdapterUnavailableError(RuntimeError):
    """Raised when an optional MLB open-source dependency is unavailable."""


LIBRARY_OPTIONS: dict[str, LibraryOption] = {
    "pybaseball": LibraryOption(
        provider="pybaseball",
        package_name="pybaseball",
        import_name="pybaseball",
        purpose="Historical/statcast-style MLB data access through pybaseball APIs.",
        capabilities=("statcast_sample", "player_lookup"),
    ),
    "mlb_statsapi": LibraryOption(
        provider="mlb_statsapi",
        package_name="MLB-StatsAPI",
        import_name="statsapi",
        purpose="Read-only MLB Stats API convenience wrapper.",
        capabilities=("team_lookup", "schedule", "player_lookup"),
    ),
    "python_mlb_statsapi": LibraryOption(
        provider="python_mlb_statsapi",
        package_name="python-mlb-statsapi",
        import_name="mlbstatsapi",
        purpose="Object-oriented wrapper around MLB Stats API data.",
        capabilities=("team_lookup", "player_lookup"),
    ),
}


def _distribution_version(package_name: str) -> str | None:
    try:
        return importlib_metadata.version(package_name)
    except importlib_metadata.PackageNotFoundError:
        return None


def _import_module(import_name: str) -> Any:
    return importlib.import_module(import_name)


def library_diagnostic(provider: str) -> AdapterDiagnostic:
    option = _library_option(provider)
    version = _distribution_version(option.package_name)
    try:
        _import_module(option.import_name)
    except Exception as exc:  # pragma: no cover - exact import failures are environment-specific.
        importable = False
        reason = (
            f"Optional dependency {option.package_name!r} is not importable as "
            f"{option.import_name!r}: {exc.__class__.__name__}: {exc}"
        )
    else:
        importable = True
        reason = (
            f"Optional dependency {option.package_name!r} is importable as "
            f"{option.import_name!r}."
        )

    installed = version is not None
    if not installed:
        status = "SKIPPED_MISSING_OPTIONAL_DEPENDENCY"
        reason = (
            f"Optional dependency {option.package_name!r} is not installed. "
            "This spike does not modify dependency files; add it only after Owner "
            "authorization."
        )
    elif not importable:
        status = "FAILED_IMPORT_ERROR"
    else:
        status = "AVAILABLE_READ_ONLY_ADAPTER"

    return AdapterDiagnostic(
        provider=option.provider,
        package_name=option.package_name,
        import_name=option.import_name,
        installed=installed,
        importable=importable,
        version=version,
        status=status,
        reason=reason,
    )


class OpenSourceMlbDataAdapter:
    """Thin read-only wrapper around optional open-source MLB data libraries."""

    def __init__(self, provider: str = "pybaseball") -> None:
        self.option = _library_option(provider)

    def diagnostic(self) -> AdapterDiagnostic:
        return library_diagnostic(self.option.provider)

    def require_library(self) -> Any:
        diagnostic = self.diagnostic()
        if diagnostic.status != "AVAILABLE_READ_ONLY_ADAPTER":
            raise AdapterUnavailableError(diagnostic.reason)
        return _import_module(self.option.import_name)

    def statcast_sample(
        self,
        start_date: str,
        end_date: str,
        *,
        max_rows: int = 5,
    ) -> dict[str, Any]:
        """Delegate statcast retrieval to pybaseball and normalize the result."""
        self._require_capability("statcast_sample")
        module = self.require_library()
        if not hasattr(module, "statcast"):
            raise AdapterUnavailableError("pybaseball.statcast is unavailable in this install.")
        result = module.statcast(start_dt=start_date, end_dt=end_date)
        return _standardized_result(
            source_library=self.option.provider,
            source_operation="statcast",
            data_kind="statcast",
            payload=result,
            max_rows=max_rows,
        )

    def team_lookup(self, name: str, *, max_rows: int = 10) -> dict[str, Any]:
        """Delegate team lookup to an installed MLB Stats API wrapper."""
        self._require_capability("team_lookup")
        module = self.require_library()
        if self.option.provider == "mlb_statsapi":
            result = module.lookup_team(name)
            operation = "lookup_team"
        else:
            mlb = module.Mlb()
            team_ids = _as_list(mlb.get_team_id(name))
            result = [mlb.get_team(team_id) for team_id in team_ids]
            operation = "Mlb.get_team_id/get_team"
        return _standardized_result(
            source_library=self.option.provider,
            source_operation=operation,
            data_kind="team",
            payload=result,
            max_rows=max_rows,
        )

    def schedule(
        self,
        start_date: str,
        end_date: str,
        *,
        team_id: int | None = None,
        max_rows: int = 10,
    ) -> dict[str, Any]:
        """Delegate schedule lookup to MLB-StatsAPI when available."""
        self._require_capability("schedule")
        module = self.require_library()
        kwargs: dict[str, Any] = {"start_date": start_date, "end_date": end_date}
        if team_id is not None:
            kwargs["team"] = team_id
        result = module.schedule(**kwargs)
        return _standardized_result(
            source_library=self.option.provider,
            source_operation="schedule",
            data_kind="schedule",
            payload=result,
            max_rows=max_rows,
        )

    def player_lookup(
        self,
        name: str,
        *,
        max_rows: int = 10,
    ) -> dict[str, Any]:
        """Delegate player metadata lookup to the selected open-source library."""
        self._require_capability("player_lookup")
        module = self.require_library()
        if self.option.provider == "pybaseball":
            parts = name.replace(",", " ").split()
            if len(parts) < 2:
                raise ValueError("pybaseball player lookup requires at least first and last name.")
            result = module.playerid_lookup(parts[-1], parts[0])
            operation = "playerid_lookup"
        elif self.option.provider == "mlb_statsapi":
            result = module.lookup_player(name)
            operation = "lookup_player"
        else:
            mlb = module.Mlb()
            person_ids = _as_list(mlb.get_people_id(name))
            result = [mlb.get_person(person_id) for person_id in person_ids]
            operation = "Mlb.get_people_id/get_person"
        return _standardized_result(
            source_library=self.option.provider,
            source_operation=operation,
            data_kind="player",
            payload=result,
            max_rows=max_rows,
        )

    def _require_capability(self, capability: str) -> None:
        if capability not in self.option.capabilities:
            raise AdapterUnavailableError(
                f"Provider {self.option.provider!r} does not expose {capability!r} "
                "through this read-only spike adapter."
            )


def available_diagnostics() -> list[dict[str, Any]]:
    return [asdict(library_diagnostic(provider)) for provider in sorted(LIBRARY_OPTIONS)]


def _library_option(provider: str) -> LibraryOption:
    try:
        return LIBRARY_OPTIONS[provider]
    except KeyError as exc:
        supported = ", ".join(sorted(LIBRARY_OPTIONS))
        raise ValueError(f"Unsupported MLB open-source provider {provider!r}; use one of {supported}.") from exc


def _standardized_result(
    *,
    source_library: str,
    source_operation: str,
    data_kind: str,
    payload: Any,
    max_rows: int,
) -> dict[str, Any]:
    records = _records(payload)
    limited_records = records[:max_rows]
    columns = sorted({key for record in limited_records for key in record})
    return {
        "disclaimer": DISCLAIMER,
        "source_library": source_library,
        "source_operation": source_operation,
        "data_kind": data_kind,
        "row_count": len(records),
        "returned_rows": len(limited_records),
        "columns": columns,
        "records": limited_records,
    }


def _records(payload: Any) -> list[dict[str, Any]]:
    normalized = _normalize(payload)
    if isinstance(normalized, list):
        return [item if isinstance(item, dict) else {"value": item} for item in normalized]
    if isinstance(normalized, dict):
        return [normalized]
    return [{"value": normalized}]


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value):
        return _normalize(asdict(value))
    if hasattr(value, "to_dict"):
        try:
            return _normalize(value.to_dict(orient="records"))
        except TypeError:
            return _normalize(value.to_dict())
    if isinstance(value, dict):
        return {str(key): _normalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple, set)):
        return [_normalize(item) for item in value]
    if hasattr(value, "__dict__"):
        return {
            str(key): _normalize(item)
            for key, item in sorted(vars(value).items())
            if not str(key).startswith("_")
        }
    return str(value)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]
