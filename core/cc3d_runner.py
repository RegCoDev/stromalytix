"""
CC3D Cloud Execution Client for Stromalytix.

All CC3D simulations run on the cloud sidecar (CC3D_API_URL).
Local execution has been removed — CC3D requires a full conda
environment that is only available on the VPS.
"""

import os
import time

CC3D_API_URL = os.environ.get("CC3D_API_URL", "")
CC3D_API_KEY = os.environ.get("CC3D_API_KEY", "")


def _extract_adhesion_value(val) -> float:
    """Extract numeric value from adhesion energy entry.

    Handles both plain numbers and confidence-tagged dicts:
    {"value": 10, "confidence": "medium"} -> 10
    """
    if isinstance(val, dict):
        return float(val.get("value", 0))
    return float(val)


def run_simulation_cloud(
    brief: dict,
    max_steps: int = 1000,
    poll_interval: float = 2.0,
    timeout: float = 180.0,
) -> dict:
    """Submit simulation to cloud sidecar, poll until complete."""
    if not CC3D_API_URL:
        return {
            "success": False,
            "ran": False,
            "error": "CC3D_API_URL not configured. Set it to your VPS sidecar address.",
            "fallback": True,
            "output": "",
            "mcs_completed": 0,
            "duration_seconds": 0.0,
        }

    import httpx

    headers = {"x-api-key": CC3D_API_KEY}

    try:
        resp = httpx.post(
            f"{CC3D_API_URL}/simulate",
            json={"brief": brief, "max_steps": max_steps},
            headers=headers,
            timeout=30.0,
        )
        resp.raise_for_status()
        job_id = resp.json()["job_id"]

        start = time.time()
        while time.time() - start < timeout:
            time.sleep(poll_interval)

            status_resp = httpx.get(
                f"{CC3D_API_URL}/job/{job_id}",
                headers=headers,
                timeout=10.0,
            )
            status_resp.raise_for_status()
            job = status_resp.json()

            if job["status"] == "complete":
                return {
                    "success": True,
                    "ran": True,
                    "vtk_frames": job.get("vtk_frames", []),
                    "metadata": job.get("metadata", {}),
                    "job_id": job_id,
                    "output": job.get("message", ""),
                    "error": "",
                    "mcs_completed": max_steps,
                    "duration_seconds": round(time.time() - start, 2),
                }
            elif job["status"] == "failed":
                return {
                    "success": False,
                    "ran": True,
                    "error": job.get("message", "Unknown error"),
                    "job_id": job_id,
                    "output": "",
                    "mcs_completed": 0,
                    "duration_seconds": round(time.time() - start, 2),
                }

        return {
            "success": False,
            "ran": True,
            "error": f"Simulation timed out after {timeout}s",
            "job_id": job_id,
            "output": "",
            "mcs_completed": 0,
            "duration_seconds": timeout,
        }

    except Exception as e:
        return {
            "success": False,
            "ran": False,
            "error": str(e),
            "output": "",
            "mcs_completed": 0,
            "duration_seconds": 0.0,
        }


def run_simulation(brief: dict, max_steps: int = 1000) -> dict:
    """Run a CC3D simulation via the cloud sidecar."""
    return run_simulation_cloud(brief, max_steps)
