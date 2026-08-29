from assistant.core.system.diagnostics import format_health_report
from assistant.core.system.health import HEALTHY, DEGRADED, HealthResult

def test_format_health_report():
    report = format_health_report([
        HealthResult("memory.database", HEALTHY, "SQLite readable."),
        HealthResult("google.calendar", DEGRADED, "Provider error."),
    ])
    assert "P.E.P.P.E.R. SYSTEM HEALTH" in report
    assert "memory.database" in report
    assert "google.calendar" in report
    assert "Overall: DEGRADED" in report
