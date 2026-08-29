"""
P.E.P.P.E.R. - World State Location

Phase 16A.5

Purpose:
    Provides one shared local-first location state for P.E.P.P.E.R.

Responsibilities:
    - retrieve the current Windows device location through WinRT
    - retain the accuracy reported by Windows
    - cache the last trusted position locally
    - return a fresh cached position immediately when appropriate
    - fall back to a recent trusted position if live Windows location fails
    - expose coordinates to weather and future location-aware services

Does NOT:
    - geocode human-readable place names
    - infer a location from conversation
    - use IP geolocation
    - transmit coordinates by itself

Named-place geocoding remains the responsibility of the weather
geocoding provider.
"""

from __future__ import annotations

import json
import math
import subprocess
import threading

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

RUNTIME_DIRECTORY = (
    PROJECT_ROOT
    / "runtime"
    / "world_state"
)

LOCATION_STATE_FILE = (
    RUNTIME_DIRECTORY
    / "location.json"
)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

# A location this fresh may be returned without querying Windows again.
DEFAULT_FRESH_SECONDS = 15 * 60

# A live Windows location less accurate than this is not accepted as a
# trusted foreground location fix.
MAX_TRUSTED_ACCURACY_METERS = 5_000.0

# If a live refresh fails, a previously trusted fix may still be useful for
# weather and timezone-level context for a limited period.
MAX_FALLBACK_AGE_SECONDS = 24 * 60 * 60

WINDOWS_LOCATION_TIMEOUT_SECONDS = 8.0


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LocationState:
    latitude: float
    longitude: float
    accuracy_m: float | None
    source: str
    captured_at: str

    altitude_m: float | None = None
    altitude_accuracy_m: float | None = None
    heading_deg: float | None = None
    speed_mps: float | None = None

    timezone: str = ""
    locality: str = ""
    region: str = ""
    country: str = ""

    @property
    def age_seconds(self) -> float:
        captured = _parse_datetime(
            self.captured_at
        )

        if captured is None:
            return float("inf")

        now = datetime.now(
            captured.tzinfo
            or timezone.utc
        )

        return max(
            0.0,
            (
                now
                - captured
            ).total_seconds(),
        )

    def is_fresh(
        self,
        max_age_seconds: float = DEFAULT_FRESH_SECONDS,
    ) -> bool:
        return (
            self.age_seconds
            <= float(
                max_age_seconds
            )
        )

    def is_trusted(
        self,
        max_accuracy_m: float = MAX_TRUSTED_ACCURACY_METERS,
    ) -> bool:
        if not (
            math.isfinite(
                self.latitude
            )
            and math.isfinite(
                self.longitude
            )
        ):
            return False

        if not (
            -90.0
            <= self.latitude
            <= 90.0
        ):
            return False

        if not (
            -180.0
            <= self.longitude
            <= 180.0
        ):
            return False

        if (
            self.accuracy_m
            is not None
        ):
            if not math.isfinite(
                self.accuracy_m
            ):
                return False

            if (
                self.accuracy_m
                > float(
                    max_accuracy_m
                )
            ):
                return False

        return True

    def to_dict(self) -> dict[str, Any]:
        return asdict(
            self
        )


# ---------------------------------------------------------------------------
# In-Process State
# ---------------------------------------------------------------------------

_STATE_LOCK = threading.RLock()
_MEMORY_STATE: LocationState | None = None

_REFRESH_LOCK = threading.Lock()
_REFRESH_THREAD: threading.Thread | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_runtime_directory():
    RUNTIME_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )


def _finite_or_none(
    value,
):
    if value is None:
        return None

    try:
        number = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(
        number
    ):
        return None

    return number


def _parse_datetime(
    value: str,
):
    text = (
        str(
            value
            or ""
        )
        .strip()
    )

    if not text:
        return None

    try:
        return datetime.fromisoformat(
            text
        )
    except ValueError:
        return None


def _state_from_mapping(
    data,
) -> LocationState | None:
    if not isinstance(
        data,
        dict,
    ):
        return None

    latitude = _finite_or_none(
        data.get(
            "latitude"
        )
    )

    longitude = _finite_or_none(
        data.get(
            "longitude"
        )
    )

    if (
        latitude is None
        or longitude is None
    ):
        return None

    captured_at = (
        str(
            data.get(
                "captured_at",
                "",
            )
            or ""
        )
        .strip()
    )

    if not captured_at:
        captured_at = (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

    state = LocationState(
        latitude=latitude,
        longitude=longitude,
        accuracy_m=_finite_or_none(
            data.get(
                "accuracy_m"
            )
        ),
        source=(
            str(
                data.get(
                    "source",
                    "windows_location",
                )
                or "windows_location"
            )
            .strip()
        ),
        captured_at=captured_at,
        altitude_m=_finite_or_none(
            data.get(
                "altitude_m"
            )
        ),
        altitude_accuracy_m=_finite_or_none(
            data.get(
                "altitude_accuracy_m"
            )
        ),
        heading_deg=_finite_or_none(
            data.get(
                "heading_deg"
            )
        ),
        speed_mps=_finite_or_none(
            data.get(
                "speed_mps"
            )
        ),
        timezone=(
            str(
                data.get(
                    "timezone",
                    "",
                )
                or ""
            )
            .strip()
        ),
        locality=(
            str(
                data.get(
                    "locality",
                    "",
                )
                or ""
            )
            .strip()
        ),
        region=(
            str(
                data.get(
                    "region",
                    "",
                )
                or ""
            )
            .strip()
        ),
        country=(
            str(
                data.get(
                    "country",
                    "",
                )
                or ""
            )
            .strip()
        ),
    )

    if not state.is_trusted():
        return None

    return state


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _save_location_state(
    state: LocationState,
):
    _ensure_runtime_directory()

    payload = state.to_dict()

    temporary_file = (
        LOCATION_STATE_FILE
        .with_suffix(
            ".tmp"
        )
    )

    temporary_file.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary_file.replace(
        LOCATION_STATE_FILE
    )


def _load_location_state_from_disk() -> LocationState | None:
    if not LOCATION_STATE_FILE.exists():
        return None

    try:
        data = json.loads(
            LOCATION_STATE_FILE.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None

    return _state_from_mapping(
        data
    )


def get_last_known_location() -> LocationState | None:
    global _MEMORY_STATE

    with _STATE_LOCK:
        if (
            _MEMORY_STATE
            is not None
            and _MEMORY_STATE.is_trusted()
        ):
            return _MEMORY_STATE

        state = (
            _load_location_state_from_disk()
        )

        if state is not None:
            _MEMORY_STATE = state

        return state


# ---------------------------------------------------------------------------
# Windows Location
# ---------------------------------------------------------------------------

_POWERSHELL_LOCATION_SCRIPT = r"""
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Runtime.WindowsRuntime

[void][Windows.Devices.Geolocation.Geolocator, Windows.Devices.Geolocation, ContentType = WindowsRuntime]

function Await-WinRT {
    param(
        [Parameter(Mandatory=$true)]
        $Operation,

        [Parameter(Mandatory=$true)]
        [Type]
        $ResultType
    )

    $asTaskMethods = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq 'AsTask' -and
            $_.IsGenericMethod -and
            $_.GetGenericArguments().Count -eq 1 -and
            $_.GetParameters().Count -eq 1
        }

    $asTaskMethod = $asTaskMethods | Select-Object -First 1

    if ($null -eq $asTaskMethod) {
        throw 'Could not locate WinRT AsTask<T> bridge.'
    }

    $genericMethod = $asTaskMethod.MakeGenericMethod($ResultType)
    $task = $genericMethod.Invoke($null, @($Operation))
    $task.Wait()

    return $task.Result
}

$accessOperation = [Windows.Devices.Geolocation.Geolocator]::RequestAccessAsync()

$access = Await-WinRT `
    -Operation $accessOperation `
    -ResultType ([Windows.Devices.Geolocation.GeolocationAccessStatus])

if ($access.ToString() -ne 'Allowed') {
    throw "Windows location access was not allowed. Status: $access"
}

$locator = New-Object Windows.Devices.Geolocation.Geolocator
$locator.DesiredAccuracy = [Windows.Devices.Geolocation.PositionAccuracy]::High
$locator.MovementThreshold = 1

$positionOperation = $locator.GetGeopositionAsync()

$position = Await-WinRT `
    -Operation $positionOperation `
    -ResultType ([Windows.Devices.Geolocation.Geoposition])

$coordinate = $position.Coordinate
$point = $coordinate.Point.Position

$result = [ordered]@{
    source = 'windows_location'
    latitude = [double]$point.Latitude
    longitude = [double]$point.Longitude
    altitude_m = [double]$point.Altitude
    accuracy_m = [double]$coordinate.Accuracy
    altitude_accuracy_m = if ($null -ne $coordinate.AltitudeAccuracy) {
        [double]$coordinate.AltitudeAccuracy
    } else {
        $null
    }
    heading_deg = if ($null -ne $coordinate.Heading) {
        [double]$coordinate.Heading
    } else {
        $null
    }
    speed_mps = if ($null -ne $coordinate.Speed) {
        [double]$coordinate.Speed
    } else {
        $null
    }
    captured_at = $coordinate.Timestamp.ToString('o')
}

$result | ConvertTo-Json -Compress
"""


def _request_windows_location() -> LocationState | None:
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                _POWERSHELL_LOCATION_SCRIPT,
            ],
            capture_output=True,
            text=True,
            timeout=WINDOWS_LOCATION_TIMEOUT_SECONDS,
            check=False,
        )
    except (
        OSError,
        subprocess.TimeoutExpired,
    ):
        return None

    if completed.returncode != 0:
        return None

    stdout = (
        completed.stdout
        or ""
    ).strip()

    if not stdout:
        return None

    payload_line = (
        stdout.splitlines()[-1]
        .strip()
    )

    try:
        data = json.loads(
            payload_line
        )
    except json.JSONDecodeError:
        return None

    return _state_from_mapping(
        data
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def refresh_current_location() -> LocationState | None:
    """
    Requests a new Windows location fix and stores it if trusted.
    """

    global _MEMORY_STATE

    state = (
        _request_windows_location()
    )

    if (
        state is None
        or not state.is_trusted()
    ):
        return None

    with _STATE_LOCK:
        _MEMORY_STATE = state

        try:
            _save_location_state(
                state
            )
        except OSError:
            # In-memory state remains valid even if persistence fails.
            pass

    return state


def get_current_location(
    *,
    max_age_seconds: float = DEFAULT_FRESH_SECONDS,
    allow_stale_fallback: bool = True,
) -> LocationState | None:
    """
    Returns the best trusted current location.

    Resolution order:
        1. fresh in-memory/disk state
        2. new Windows location fix
        3. recent trusted cached fallback, if allowed

    This function never falls back to a user weather preference. That policy
    belongs to the caller because location state is shared by more than weather.
    """

    cached = (
        get_last_known_location()
    )

    if (
        cached is not None
        and cached.is_fresh(
            max_age_seconds
        )
    ):
        return cached

    refreshed = (
        refresh_current_location()
    )

    if refreshed is not None:
        return refreshed

    if (
        allow_stale_fallback
        and cached is not None
        and cached.age_seconds
        <= MAX_FALLBACK_AGE_SECONDS
        and cached.is_trusted()
    ):
        return cached

    return None


def _background_refresh_worker():
    global _REFRESH_THREAD

    try:
        refresh_current_location()

    finally:
        with _REFRESH_LOCK:
            _REFRESH_THREAD = None


def request_location_refresh_in_background() -> bool:
    """
    Starts one daemon refresh when another refresh is not already running.

    Returns True when a new refresh thread was started.
    """

    global _REFRESH_THREAD

    with _REFRESH_LOCK:
        if (
            _REFRESH_THREAD is not None
            and _REFRESH_THREAD.is_alive()
        ):
            return False

        thread = threading.Thread(
            target=_background_refresh_worker,
            name="pepper-location-refresh",
            daemon=True,
        )

        _REFRESH_THREAD = thread
        thread.start()

        return True


def get_foreground_location(
    *,
    fresh_seconds: float = DEFAULT_FRESH_SECONDS,
    max_cached_age_seconds: float = MAX_FALLBACK_AGE_SECONDS,
) -> LocationState | None:
    """
    Returns trusted cached location without blocking the foreground request.

    If the cached fix is stale, a Windows refresh is started in the
    background while the cached fix is returned immediately.

    If no trusted cache exists, a background refresh is started and None is
    returned immediately so the caller can use its own fallback policy.
    """

    cached = get_last_known_location()

    if cached is None:
        request_location_refresh_in_background()
        return None

    if not cached.is_fresh(
        fresh_seconds
    ):
        request_location_refresh_in_background()

    if (
        cached.age_seconds
        <= float(
            max_cached_age_seconds
        )
        and cached.is_trusted()
    ):
        return cached

    return None


# ---------------------------------------------------------------------------
# Diagnostic
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(
        "P.E.P.P.E.R. World State - Location"
    )

    print(
        "-------------------------------"
    )

    state = get_current_location(
        max_age_seconds=0,
        allow_stale_fallback=True,
    )

    if state is None:
        print(
            "No trusted location is available."
        )
    else:
        print(
            json.dumps(
                state.to_dict(),
                indent=2,
                ensure_ascii=False,
            )
        )
