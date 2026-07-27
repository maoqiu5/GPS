from pathlib import Path

source = Path("scripts/gps_query_api.py").read_text(encoding="utf-8")

for endpoint in ["/api/truck-stations", "/api/truck-market-references", "/api/truck-distance"]:
    assert endpoint not in source, f"{endpoint} should be removed from GPS API"

assert "/api/trajectory" in source
assert "/api/trajectory-devices" in source
assert "/api/route-summary" in source
print("gps-only api smoke passed")
