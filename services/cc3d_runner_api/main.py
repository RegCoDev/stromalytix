"""
CC3D Execution Sidecar — FastAPI

Receives simulation briefs from Stromalytix Streamlit app,
executes CC3D simulations, returns VTK output.

Deploy on: Hostinger VPS / Fly.io / any Linux server with CC3D conda env.

Security: API key auth. Never expose without STROMALYTIX_API_KEY.
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
import asyncio
import uuid
import os
from pathlib import Path

app = FastAPI(title="Stromalytix CC3D Runner")

# In-memory job store (Redis in production)
jobs = {}
STROMALYTIX_API_KEY = os.environ.get("STROMALYTIX_API_KEY", "dev-key-change-me")
CC3D_PYTHON = os.environ.get(
    "CC3D_PYTHON", "/opt/miniconda3/envs/cc3d/bin/python"
)


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
    """Health check — returns CC3D availability."""
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
    jobs[job_id] = {
        "status": "queued",
        "message": "Job queued",
        "vtk_frames": [],
        "metadata": {},
    }

    asyncio.create_task(_run_simulation(job_id, req))

    return {"job_id": job_id, "status": "queued"}


@app.get("/job/{job_id}")
async def get_job_status(
    job_id: str,
    _key: str = Depends(verify_api_key),
):
    """Poll job status. Returns VTK frames when complete."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.delete("/job/{job_id}")
async def cancel_job(
    job_id: str,
    _key: str = Depends(verify_api_key),
):
    if job_id in jobs:
        jobs[job_id]["status"] = "cancelled"
    return {"cancelled": True}


async def _run_simulation(job_id: str, req: SimulationRequest):
    """Execute CC3D simulation, capture VTK output."""
    from runner import generate_cc3d_script, execute_cc3d, collect_vtk_output

    jobs[job_id]["status"] = "running"
    jobs[job_id]["message"] = "Generating CC3D script..."

    try:
        job_dir = Path(f"/tmp/cc3d_jobs/{job_id}")
        job_dir.mkdir(parents=True, exist_ok=True)

        script_path = job_dir / "simulation.py"
        script_content = generate_cc3d_script(
            req.brief,
            max_steps=req.max_steps,
            output_frequency=req.output_frequency,
        )

        _validate_script(script_content)
        script_path.write_text(script_content)

        jobs[job_id]["message"] = "Running CC3D simulation..."

        success, stdout, stderr = await execute_cc3d(
            CC3D_PYTHON, script_path, job_dir, timeout=120
        )

        if not success:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["message"] = f"CC3D execution failed: {stderr[:500]}"
            return

        jobs[job_id]["message"] = "Processing simulation output..."
        vtk_frames = collect_vtk_output(job_dir)

        jobs[job_id]["status"] = "complete"
        jobs[job_id]["vtk_frames"] = vtk_frames
        jobs[job_id]["metadata"] = {
            "n_frames": len(vtk_frames),
            "max_steps": req.max_steps,
            "cell_types": req.brief.get("cell_types", []),
        }
        jobs[job_id]["message"] = f"Complete. {len(vtk_frames)} frames."

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["message"] = f"Error: {str(e)}"


def _validate_script(script: str):
    """Security: reject scripts with dangerous patterns."""
    forbidden = [
        "import os", "import sys", "subprocess",
        "eval(", "exec(", "__import__", "open(",
        "socket", "requests", "urllib",
    ]
    for pattern in forbidden:
        if pattern in script:
            raise ValueError(
                f"Forbidden pattern in generated script: {pattern}"
            )
