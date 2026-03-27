"""
CC3D Cloud Execution Client for Stromalytix.

All CC3D simulations run on the cloud sidecar (CC3D_API_URL).
Local execution has been removed — CC3D requires a full conda
environment that is only available on the VPS.
"""

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

CC3D_API_URL = os.environ.get("CC3D_API_URL", "")
CC3D_API_KEY = os.environ.get("CC3D_API_KEY", "")


# region agent log
def _agent_cc3d_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    """Debug NDJSON (session 579e47); also prints for Streamlit Cloud log capture."""
    entry = {
        "sessionId": "579e47",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    line = json.dumps(entry, default=str)
    try:
        log_path = Path(__file__).resolve().parent.parent / "debug-579e47.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    print(f"[AGENT_DBG_CC3D] {line}", flush=True)


# endregion


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
    _api_host = urlparse(CC3D_API_URL.rstrip("/")).netloc or "?"

    try:
        _agent_cc3d_log(
            "H5",
            "cc3d_runner.py:run_simulation_cloud:entry",
            "cloud_run_start",
            {
                "api_host": _api_host,
                "max_steps": max_steps,
                "client_timeout_s": timeout,
                "poll_interval_s": poll_interval,
                "brief_top_keys": list(brief.keys())[:12] if isinstance(brief, dict) else [],
            },
        )

        t_post0 = time.time()
        resp = httpx.post(
            f"{CC3D_API_URL}/simulate",
            json={"brief": brief, "max_steps": max_steps},
            headers=headers,
            timeout=30.0,
        )
        resp.raise_for_status()
        job_id = resp.json()["job_id"]
        _agent_cc3d_log(
            "H5",
            "cc3d_runner.py:run_simulation_cloud:post_ok",
            "job_submitted",
            {
                "job_id": job_id,
                "http_status": resp.status_code,
                "post_elapsed_s": round(time.time() - t_post0, 2),
            },
        )

        start = time.time()
        poll_count = 0
        last_status = None
        last_message = ""
        prev_logged_status: object | None = None
        while time.time() - start < timeout:
            time.sleep(poll_interval)

            status_resp = httpx.get(
                f"{CC3D_API_URL}/job/{job_id}",
                headers=headers,
                timeout=10.0,
            )
            status_resp.raise_for_status()
            job = status_resp.json()
            poll_count += 1
            last_status = job.get("status")
            last_message = (job.get("message") or "")[:200]

            if poll_count == 1 or poll_count % 5 == 0 or last_status != prev_logged_status:
                _agent_cc3d_log(
                    "H4",
                    "cc3d_runner.py:run_simulation_cloud:poll",
                    "job_poll",
                    {
                        "job_id": job_id,
                        "poll": poll_count,
                        "status": last_status,
                        "message_preview": last_message,
                        "elapsed_s": round(time.time() - start, 2),
                    },
                )
                prev_logged_status = last_status

            if job["status"] == "complete":
                _agent_cc3d_log(
                    "H1",
                    "cc3d_runner.py:run_simulation_cloud:complete",
                    "job_complete",
                    {
                        "job_id": job_id,
                        "polls": poll_count,
                        "elapsed_s": round(time.time() - start, 2),
                    },
                )
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
                _agent_cc3d_log(
                    "H3",
                    "cc3d_runner.py:run_simulation_cloud:failed",
                    "job_failed",
                    {
                        "job_id": job_id,
                        "polls": poll_count,
                        "server_message_preview": (job.get("message") or "")[:400],
                    },
                )
                return {
                    "success": False,
                    "ran": True,
                    "error": job.get("message", "Unknown error"),
                    "job_id": job_id,
                    "output": "",
                    "mcs_completed": 0,
                    "duration_seconds": round(time.time() - start, 2),
                }

        _agent_cc3d_log(
            "H1",
            "cc3d_runner.py:run_simulation_cloud:client_timeout",
            "poll_exhausted",
            {
                "job_id": job_id,
                "last_status": last_status,
                "last_message_preview": last_message,
                "polls": poll_count,
                "client_timeout_s": timeout,
                "elapsed_s": round(time.time() - start, 2),
            },
        )
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
        _agent_cc3d_log(
            "H2",
            "cc3d_runner.py:run_simulation_cloud:exception",
            "httpx_or_other_error",
            {
                "exc_type": type(e).__name__,
                "exc_str": str(e)[:500],
                "api_host": _api_host,
            },
        )
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
