"""
CC3D script generation and execution for the sidecar service.
"""

import asyncio
import base64
from pathlib import Path


def generate_cc3d_script(
    brief: dict,
    max_steps: int = 1000,
    output_frequency: int = 100,
) -> str:
    """
    Generate CC3D Python simulation script from brief dict.

    Input validation:
    - Cell type names: alphanumeric + underscore only
    - All numeric params within biological ranges
    - Max 5 cell types (performance)
    """
    cell_types = brief.get("cell_types", ["Cell1"])

    # Sanitize cell type names
    cell_types = [
        "".join(c for c in ct if c.isalnum() or c == "_")[:20]
        for ct in cell_types[:5]
    ]
    if not cell_types:
        cell_types = ["Cell1"]

    # Extract parameters with biological range validation
    adhesion_energy = max(1, min(100, brief.get("adhesion_energy", 10)))
    lambda_vol = max(1, min(10, brief.get("lambda_volume", 2.0)))
    target_vol = max(10, min(1000, brief.get("target_volume", 50)))
    stiffness = max(0.1, min(100, brief.get("stiffness_kpa", 5.0)))

    cell_type_defs = "\n        ".join([
        f'self.cell_type["{ct}"] = self.cell_type["{ct}"]'
        for ct in cell_types
    ])

    class_name = cell_types[0].replace(" ", "_")

    return f'''
from cc3d.core.PySteppables import *

class {class_name}Steppable(SteppableBasePy):
    def __init__(self, frequency=1):
        SteppableBasePy.__init__(self, frequency)

    def start(self):
        for i in range(20):
            cell = self.new_cell(self.CELL1)
            self.cell_field[i*5:i*5+5, 0:5, 0:5] = cell
            cell.targetVolume = {target_vol}
            cell.lambdaVolume = {lambda_vol}

    def step(self, mcs):
        for cell in self.cell_list:
            cell.targetVolume = {target_vol}
            cell.lambdaVolume = {lambda_vol}

CompuCellSetup.register_steppable(
    steppable={class_name}Steppable(frequency=1)
)
'''


async def execute_cc3d(
    cc3d_python: str,
    script_path: Path,
    output_dir: Path,
    timeout: int = 120,
):
    """Execute CC3D script headlessly, capture output."""
    try:
        proc = await asyncio.create_subprocess_exec(
            cc3d_python, str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(output_dir),
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        success = proc.returncode == 0
        return success, stdout.decode(), stderr.decode()
    except asyncio.TimeoutError:
        return False, "", "Simulation timed out"
    except Exception as e:
        return False, "", str(e)


def collect_vtk_output(job_dir: Path) -> list:
    """Find VTK files, encode as base64 for JSON transport."""
    vtk_files = sorted(job_dir.rglob("*.vtk"))
    frames = []
    for vtk_path in vtk_files[:10]:  # max 10 frames
        content = vtk_path.read_bytes()
        frames.append({
            "filename": vtk_path.name,
            "data_b64": base64.b64encode(content).decode(),
            "size_bytes": len(content),
        })
    return frames
