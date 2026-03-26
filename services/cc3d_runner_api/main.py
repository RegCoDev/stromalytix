"""
CC3D Execution Sidecar - FastAPI

Receives simulation briefs from Stromalytix Streamlit app,
executes CC3D simulations, returns VTK output.

Deploy on: Hostinger VPS / Fly.io / any Linux server with CC3D conda env.

Security: API key auth. Never expose without STROMALYTIX_API_KEY.
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
import asyncio
import json
import sqlite3
import time
import uuid
import os
from pathlib import Path

app = FastAPI(title="Stromalytix CC3D Runner")

STROMALYTIX_API_KEY = os.environ.get("STROMALYTIX_API_KEY", "dev-key-change-me")
CC3D_PYTHON = os.environ.get(
    "CC3D_PYTHON", "/opt/miniconda3/envs/cc3d/bin/python"
)
DB_PATH = os.environ.get("CC3D_JOBS_DB", "jobs.db")

# Internet-facing VPS: set STROMALYTIX_ENFORCE_API_KEY=1 and a strong STROMALYTIX_API_KEY.
_INSECURE_API_KEYS = frozenset({
    "dev-key-change-me",
    "change-me-in-production",
    "CHANGE_ME_BEFORE_DEPLOY",
})
_enforce = os.environ.get("STROMALYTIX_ENFORCE_API_KEY", "").lower() in ("1", "true", "yes")
_allow_weak = os.environ.get("STROMALYTIX_ALLOW_WEAK_KEY", "").lower() in ("1", "true", "yes")
if _enforce and STROMALYTIX_API_KEY in _INSECURE_API_KEYS and not _allow_weak:
    raise SystemExit(
        "STROMALYTIX_API_KEY is a placeholder. Set a strong secret (same as Streamlit CC3D_API_KEY). "
        "For local dev: unset STROMALYTIX_ENFORCE_API_KEY or set STROMALYTIX_ALLOW_WEAK_KEY=1."
    )

# --------------- SQLite job store ---------------

_JOB_TTL_SECONDS = 3600  # auto-clean jobs older than 1 hour


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id          TEXT PRIMARY KEY,
            status      TEXT NOT NULL DEFAULT 'queued',
            message     TEXT NOT NULL DEFAULT '',
            vtk_frames  TEXT NOT NULL DEFAULT '[]',
            metadata    TEXT NOT NULL DEFAULT '{}',
            created_at  REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


_db = _get_db()


def _cleanup_old_jobs():
    cutoff = time.time() - _JOB_TTL_SECONDS
    _db.execute("DELETE FROM jobs WHERE created_at < ?", (cutoff,))
    _db.commit()


def _create_job(job_id: str):
    _cleanup_old_jobs()
    _db.execute(
        "INSERT INTO jobs (id, status, message, vtk_frames, metadata, created_at) "
        "VALUES (?, 'queued', 'Job queued', '[]', '{}', ?)",
        (job_id, time.time()),
    )
    _db.commit()


def _update_job(job_id: str, **fields):
    """Update one or more columns for a job. vtk_frames/metadata auto-serialised."""
    if "vtk_frames" in fields:
        fields["vtk_frames"] = json.dumps(fields["vtk_frames"])
    if "metadata" in fields:
        fields["metadata"] = json.dumps(fields["metadata"])
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [job_id]
    _db.execute(f"UPDATE jobs SET {sets} WHERE id = ?", vals)
    _db.commit()


def _get_job(job_id: str) -> dict | None:
    row = _db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    return {
        "status": row["status"],
        "message": row["message"],
        "vtk_frames": json.loads(row["vtk_frames"]),
        "metadata": json.loads(row["metadata"]),
    }


class SimulationRequest(BaseModel):
    brief: dict
    max_steps: int = 1000
    output_frequency: int = 100


def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != STROMALYTIX_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


@app.get("/health")
async def health():
    """Health check â€” returns CC3D availability."""
    cc3d_available = Path(CC3D_PYTHON).exists()
    return {
        "status": "ok",
        "cc3d_available": cc3d_available,
        "cc3d_python": CC3D_PYTHON,
    }


@app.post("/simulate")
async def submit_simulation(
    req: SimulationRequest,
    _key: str = Depends(verify_api_key),
):
    """Submit simulation job. Returns job_id immediately."""
    job_id = str(uuid.uuid4())
    _create_job(job_id)

    asyncio.create_task(_run_simulation(job_id, req))

    return {"job_id": job_id, "status": "queued"}


@app.get("/job/{job_id}")
async def get_job_status(
    job_id: str,
    _key: str = Depends(verify_api_key),
):
    """Poll job status. Returns VTK frames when complete."""
    job = _get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.delete("/job/{job_id}")
async def cancel_job(
    job_id: str,
    _key: str = Depends(verify_api_key),
):
    job = _get_job(job_id)
    if job is not None:
        _update_job(job_id, status="cancelled")
    return {"cancelled": True}


async def _run_simulation(job_id: str, req: SimulationRequest):
    """Execute CC3D simulation via project XML + steppable + PIF."""
    from runner import generate_cc3d_project, execute_cc3d, collect_vtk_output

    _update_job(job_id, status="running", message="Generating CC3D project...")

    try:
        job_dir = Path(f"/tmp/cc3d_jobs/{job_id}")
        job_dir.mkdir(parents=True, exist_ok=True)

        steppable_py, project_xml, pif_content = generate_cc3d_project(
            req.brief,
            max_steps=req.max_steps,
            output_frequency=req.output_frequency,
        )

        _validate_script(steppable_py)

        (job_dir / "Simulation" / "Simulation.py").parent.mkdir(exist_ok=True)
        (job_dir / "Simulation" / "Simulation.py").write_text(steppable_py, encoding="utf-8")
        (job_dir / "simulation.xml").write_text(project_xml, encoding="utf-8")

        if pif_content:
            (job_dir / "simulation.pif").write_text(pif_content, encoding="utf-8")

        # CC3D project file that ties everything together
        cc3d_project = f"""<Simulation version="4.0.0">
  <XMLScript Type="XMLScript">simulation.xml</XMLScript>
  <PythonScript Type="PythonScript">Simulation/Simulation.py</PythonScript>
</Simulation>
"""
        (job_dir / "simulation.cc3d").write_text(cc3d_project, encoding="utf-8")

        _update_job(job_id, message="Running CC3D simulation...")

        cc3d_runner = os.environ.get("CC3D_RUNNER", CC3D_PYTHON)
        script_path = job_dir / "simulation.cc3d"
        success, stdout, stderr = await execute_cc3d(
            cc3d_runner, script_path, job_dir, timeout=120
        )

        if not success:
            _update_job(job_id, status="failed",
                        message=f"CC3D execution failed: {stderr[:500]}")
            return

        _update_job(job_id, message="Processing simulation output...")
        vtk_frames = collect_vtk_output(job_dir)

        cell_frames = [f for f in vtk_frames if f.get("field_type") == "cell"]
        o2_frames = [f for f in vtk_frames if f.get("field_type") == "o2"]

        _update_job(
            job_id,
            status="complete",
            vtk_frames=vtk_frames,
            metadata={
                "n_cell_frames": len(cell_frames),
                "n_o2_frames": len(o2_frames),
                "n_total_frames": len(vtk_frames),
                "max_steps": req.max_steps,
                "cell_types": req.brief.get("key_parameters", {}).get("cell_types", []),
            },
            message=f"Complete. {len(cell_frames)} cell frames, {len(o2_frames)} O2 frames.",
        )

    except Exception as e:
        _update_job(job_id, status="failed", message=f"Error: {str(e)}")


def _validate_script(script: str):
    """Security: reject scripts with dangerous patterns.

    Uses regex to match actual import statements and function calls,
    not accidental matches inside string literals or CC3D framework code.
    """
    import re

    # Patterns that match real import/call-level usage, not string contents
    forbidden_patterns = [
        (r'^\s*import\s+(os|sys|subprocess|socket|shutil|pathlib|glob|requests|urllib)\b', "forbidden import"),
        (r'^\s*from\s+(os|sys|subprocess|socket|shutil|pathlib|glob|requests|urllib)\b', "forbidden from-import"),
        (r'\b(eval|exec|__import__)\s*\(', "forbidden builtin call"),
        (r'\b(subprocess|shutil)\s*\.', "forbidden module access"),
    ]

    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        for pattern, label in forbidden_patterns:
            if re.search(pattern, line):
                raise ValueError(f"Blocked: {label} in: {line.strip()[:80]}")
