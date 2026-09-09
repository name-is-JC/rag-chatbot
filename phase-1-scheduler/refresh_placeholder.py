"""Phase 1 placeholder for the daily refresh job.

Proves the GitHub Actions scheduling + commit-back mechanics work end to end.
Replaced by the real ingestion pipeline in Phase 2 (see Docs/Ingestion-Architecture.md);
the workflow file that calls this script will be updated to call the Phase 2
entry point instead, without changing the scheduling/commit logic around it.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

output_path = Path("data/last_refresh.json")
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(
    json.dumps({"last_run_utc": datetime.now(timezone.utc).isoformat()}, indent=2)
)
