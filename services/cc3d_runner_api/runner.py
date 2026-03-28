"""
CC3D project generation and execution for the sidecar service.

Generates a complete CC3D project: Python steppable + XML configuration +
optional PIF file for scaffold initialisation. Supports O2 diffusion,
proliferation via MitosisSteppable, media change events, periodic
boundary conditions, and dual scaffold representation (frozen cells for
rigid scaffolds, ECM density field for gels).
"""

import asyncio
import base64
from pathlib import Path
from typing import Optional


def _extract_val(val) -> float:
    """Extract numeric value from plain number or confidence-tagged dict."""
    if isinstance(val, dict):
        return float(val.get("value", 0))
    return float(val)


def _sanitize(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c == "_")[:20] or "Cell"


# ---------------------------------------------------------------------------
# CC3D project XML generation
# ---------------------------------------------------------------------------

def _generate_project_xml(
    dims: tuple[int, int, int],
    cell_types: list[str],
    adhesion_matrix: dict[str, float],
    mcs_steps: int,
    pbc_axes: list[str],
    has_o2: bool,
    o2_diffusion: float,
    o2_decay: float,
    o2_boundary: float,
    has_ecm_field: bool,
    has_pif: bool = False,
    potts_temperature: float = 10.0,
    neighbor_order: int = 2,
) -> str:
    """Generate CC3D Simulation XML (.cc3d project file content)."""

    # Boundary conditions
    bc_lines = []
    for axis in ("x", "y", "z"):
        if axis in pbc_axes:
            bc_lines.append(f'      <Plane Axis="{axis.upper()}"><Periodic/></Plane>')
        else:
            bc_lines.append(f'      <Plane Axis="{axis.upper()}"><NoFlux/></Plane>')
    bc_block = "\n".join(bc_lines)

    # Cell type declarations
    type_lines = ['    <CellType TypeId="0" TypeName="Medium"/>']
    type_lines.append('    <CellType TypeId="1" TypeName="Scaffold" Freeze=""/>')
    for i, ct in enumerate(cell_types):
        type_lines.append(f'    <CellType TypeId="{i + 2}" TypeName="{ct}"/>')
    type_block = "\n".join(type_lines)

    # Contact energies (adhesion matrix)
    contact_lines = []
    all_types = ["Medium", "Scaffold"] + cell_types
    for i, t1 in enumerate(all_types):
        for t2 in all_types[i:]:
            key = f"{t1}_{t2}"
            alt_key = f"{t2}_{t1}"
            energy = adhesion_matrix.get(key, adhesion_matrix.get(alt_key, 10))
            contact_lines.append(
                f'    <Energy Type1="{t1}" Type2="{t2}">{energy}</Energy>'
            )
    contact_block = "\n".join(contact_lines)

    # Diffusion solver for O2
    o2_solver = ""
    if has_o2:
        o2_solver = f"""
  <Steppable Type="DiffusionSolverFE">
    <DiffusionField Name="O2">
      <DiffusionData>
        <FieldName>O2</FieldName>
        <DiffusionConstant>{o2_diffusion}</DiffusionConstant>
        <DecayConstant>{o2_decay}</DecayConstant>
      </DiffusionData>
      <BoundaryConditions>
        <Plane Axis="X">
          <ConstantValue PlanePosition="Min" Value="{o2_boundary}"/>
          <ConstantValue PlanePosition="Max" Value="{o2_boundary}"/>
        </Plane>
        <Plane Axis="Y">
          <ConstantValue PlanePosition="Min" Value="{o2_boundary}"/>
          <ConstantValue PlanePosition="Max" Value="{o2_boundary}"/>
        </Plane>
        <Plane Axis="Z">
          <ConstantValue PlanePosition="Min" Value="{o2_boundary}"/>
          <ConstantValue PlanePosition="Max" Value="{o2_boundary}"/>
        </Plane>
      </BoundaryConditions>
    </DiffusionField>
  </Steppable>"""

    ecm_solver = ""
    if has_ecm_field:
        ecm_solver = """
  <Steppable Type="DiffusionSolverFE">
    <DiffusionField Name="ECM_density">
      <DiffusionData>
        <FieldName>ECM_density</FieldName>
        <DiffusionConstant>0</DiffusionConstant>
        <DecayConstant>0</DecayConstant>
      </DiffusionData>
    </DiffusionField>
  </Steppable>"""

    pif_block = ""
    if has_pif:
        pif_block = """
  <Steppable Type="PIFInitializer">
    <PIFName>simulation.pif</PIFName>
  </Steppable>"""

    xml = f"""<CompuCell3D Version="4.0.0">
  <Potts>
    <Dimensions x="{dims[0]}" y="{dims[1]}" z="{dims[2]}"/>
    <Steps>{mcs_steps}</Steps>
    <Temperature>{potts_temperature}</Temperature>
    <NeighborOrder>{neighbor_order}</NeighborOrder>
    <BoundaryConditions>
{bc_block}
    </BoundaryConditions>
  </Potts>

  <Plugin Name="CellType">
{type_block}
  </Plugin>

  <Plugin Name="Volume">
    <VolumeEnergyParameters CellType="Scaffold" TargetVolume="25" LambdaVolume="100"/>
  </Plugin>

  <Plugin Name="Surface"/>

  <Plugin Name="Contact">
{contact_block}
  </Plugin>

  <Plugin Name="PixelTracker"/>
{o2_solver}{ecm_solver}{pif_block}
</CompuCell3D>
"""
    return xml


# ---------------------------------------------------------------------------
# Python steppable generation
# ---------------------------------------------------------------------------

def _generate_steppable_py(
    cell_types: list[str],
    target_vol: float,
    lambda_vol: float,
    target_surf: float,
    lambda_surf: float,
    mcs_steps: int,
    vtk_output_freq: int,
    has_o2: bool,
    o2_consumption_rate: float,
    o2_boundary_value: float,
    doubling_time_mcs: float,
    contact_inhibition_neighbors: int,
    media_change_mcs: list[int],
    scaffold_type: str,
    ecm_degradation_rate: float,
    dims: tuple[int, int, int] = (100, 100, 100),
) -> str:
    """Generate the Python steppable file."""

    cell_types_repr = repr(cell_types)
    media_changes_repr = repr(media_change_mcs)

    # Compute safe seeding: fit cells within lattice bounds
    grid_side = 5
    n_types = max(len(cell_types), 1)
    # Available slots per axis (leave margin)
    usable_x = max(dims[0] - grid_side, grid_side)
    usable_y = max(dims[1] - grid_side, grid_side)
    usable_z = max(dims[2] - grid_side, grid_side)
    # Slots along x per cell type
    slots_x = usable_x // (grid_side * n_types)
    slots_y = usable_y // grid_side
    # Total safe slots per type = grid along x * grid along y
    cells_per_type = max(3, min(slots_x * max(1, slots_y // 4), 30))

    seed_lines = []
    for idx, ct in enumerate(cell_types):
        x_start = idx * (usable_x // n_types)
        x_end = x_start + (usable_x // n_types) - grid_side
        seed_lines.append(f"        # Seed {ct}")
        seed_lines.append(f"        _nx = max(1, ({x_end} - {x_start}) // {grid_side})")
        seed_lines.append(f"        for i in range({cells_per_type}):")
        seed_lines.append(f"            cell = self.new_cell(self.{ct.upper()})")
        seed_lines.append(f"            ix = i % _nx")
        seed_lines.append(f"            iy = i // _nx")
        seed_lines.append(f"            x0 = {x_start} + ix * {grid_side}")
        seed_lines.append(f"            y0 = iy * {grid_side}")
        seed_lines.append(f"            if x0 + {grid_side} > {dims[0]} or y0 + {grid_side} > {dims[1]}:")
        seed_lines.append(f"                continue")
        seed_lines.append(f"            self.cell_field[x0:x0+{grid_side}, y0:y0+{grid_side}, 0:{min(grid_side, dims[2])}] = cell")
        seed_lines.append(f"            cell.targetVolume = {target_vol}")
        seed_lines.append(f"            cell.lambdaVolume = {lambda_vol}")
        seed_lines.append(f"            cell.targetSurface = {target_surf}")
        seed_lines.append(f"            cell.lambdaSurface = {lambda_surf}")
    seed_block = "\n".join(seed_lines)

    o2_uptake_block = ""
    if has_o2:
        o2_uptake_block = f"""
        # O2 uptake by cells
        o2_field = self.field.O2
        for cell in self.cell_list:
            x, y, z = int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)
            if 0 <= x < self.dim.x and 0 <= y < self.dim.y and 0 <= z < self.dim.z:
                local_o2 = o2_field[x, y, z]
                uptake = min(local_o2, {o2_consumption_rate})
                o2_field[x, y, z] = max(0, local_o2 - uptake)"""

    proliferation_block = ""
    if doubling_time_mcs > 0:
        o2_check = ""
        if has_o2:
            o2_check = """
            x, y, z = int(cell.xCOM), int(cell.yCOM), int(cell.zCOM)
            if 0 <= x < self.dim.x and 0 <= y < self.dim.y and 0 <= z < self.dim.z:
                local_o2 = o2_field[x, y, z]
                o2_factor = local_o2 / (local_o2 + 0.02)  # Hill function, K_m = 2% O2
            else:
                o2_factor = 1.0"""
        else:
            o2_check = """
            o2_factor = 1.0"""

        proliferation_block = f"""
        # Proliferation: grow toward division
        growth_rate = {target_vol} / {doubling_time_mcs}
        for cell in self.cell_list_by_type(*[getattr(self, ct.upper()) for ct in CELL_TYPES]):
            neighbor_count = len(self.get_cell_neighbor_data_list(cell))
            if neighbor_count > {contact_inhibition_neighbors}:
                continue
{o2_check}
            cell.targetVolume += growth_rate * o2_factor"""

    media_change_block = ""
    if media_change_mcs:
        media_change_block = f"""
        # Media change events
        if mcs in self.MEDIA_CHANGE_SCHEDULE:
            if {has_o2}:
                o2_field = self.field.O2
                for x in range(self.dim.x):
                    for y in range(self.dim.y):
                        for z_pos in [0, self.dim.z - 1]:
                            o2_field[x, y, z_pos] = {o2_boundary_value}
                for x in range(self.dim.x):
                    for z_pos in range(self.dim.z):
                        for y_pos in [0, self.dim.y - 1]:
                            o2_field[x, y_pos, z_pos] = {o2_boundary_value}
                for y in range(self.dim.y):
                    for z_pos in range(self.dim.z):
                        for x_pos in [0, self.dim.x - 1]:
                            o2_field[x_pos, y, z_pos] = {o2_boundary_value}
            print(f"Media change at MCS {{mcs}}")"""

    ecm_degradation_block = ""
    if scaffold_type in ("degradable", "hybrid") and ecm_degradation_rate > 0:
        ecm_degradation_block = f"""
        # ECM degradation (hydrolytic)
        ecm_field = self.field.ECM_density
        for x in range(self.dim.x):
            for y in range(self.dim.y):
                for z_pos in range(self.dim.z):
                    if ecm_field[x, y, z_pos] > 0:
                        ecm_field[x, y, z_pos] *= (1.0 - {ecm_degradation_rate})"""

    mitosis_class = ""
    if doubling_time_mcs > 0:
        mitosis_class = f"""

class StromalytixMitosisSteppable(_PySteppables.MitosisSteppablePy):
    def __init__(self, frequency=10):
        super().__init__(frequency)

    def step(self, mcs):
        cells_to_divide = []
        for cell in self.cell_list:
            if cell.volume > 2 * {target_vol}:
                cells_to_divide.append(cell)
        for cell in cells_to_divide:
            self.divide_cell_random_orientation(cell)

    def update_attributes(self):
        self.parent_cell.targetVolume = {target_vol}
        self.parent_cell.lambdaVolume = {lambda_vol}
        self.parent_cell.targetSurface = {target_surf}
        self.parent_cell.lambdaSurface = {lambda_surf}
        self.clone_parent_2_child()


CompuCellSetup.register_steppable(
    steppable=StromalytixMitosisSteppable(frequency=10)
)"""

    mitosis_import = ""
    if doubling_time_mcs > 0:
        mitosis_import = "\nimport cc3d.core.PySteppables as _PySteppables"

    # Build inline type ID list for step() — avoids module-level variable scope issues with CC3D exec()
    type_attrs = ", ".join(f"self.{ct.upper()}" for ct in cell_types)

    # Also inline references in proliferation block
    proliferation_block = proliferation_block.replace(
        "*[getattr(self, ct.upper()) for ct in CELL_TYPES]",
        type_attrs,
    )

    script = f'''"""Auto-generated CC3D simulation — Stromalytix sidecar."""
import cc3d.core.PySteppables as _PySteppables
from cc3d import CompuCellSetup{mitosis_import}


class StromalytixSteppable(_PySteppables.SteppableBasePy):
    CELL_TYPES = {cell_types_repr}
    TARGET_VOLUME = {target_vol}
    LAMBDA_VOLUME = {lambda_vol}
    TARGET_SURFACE = {target_surf}
    LAMBDA_SURFACE = {lambda_surf}
    MCS_STEPS = {mcs_steps}
    VTK_OUTPUT_FREQ = {vtk_output_freq}
    MEDIA_CHANGE_SCHEDULE = {media_changes_repr}

    def __init__(self, frequency=1):
        super().__init__(frequency)

    def start(self):
{seed_block}
        print(f"Seeded {{sum(1 for _ in self.cell_list)}} cells")

    def step(self, mcs):
        for cell in self.cell_list_by_type({type_attrs}):
            cell.targetSurface = self.TARGET_SURFACE
            cell.lambdaSurface = self.LAMBDA_SURFACE
{o2_uptake_block}{proliferation_block}{media_change_block}{ecm_degradation_block}

        if mcs % self.VTK_OUTPUT_FREQ == 0:
            print(f"MCS {{mcs}}/{{self.MCS_STEPS}}")


CompuCellSetup.register_steppable(
    steppable=StromalytixSteppable(frequency=1)
){mitosis_class}

CompuCellSetup.run()
'''
    return script


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_cc3d_project(
    brief: dict,
    max_steps: int = 1000,
    output_frequency: int = 100,
    pif_content: Optional[str] = None,
) -> tuple[str, str, str]:
    """Generate a complete CC3D project from a simulation brief.

    Returns (steppable_py, project_xml, pif_content).
    """
    params = brief.get("key_parameters", brief)

    # Cell types
    cell_types_raw = params.get("cell_types", ["Cell_A", "Cell_B"])
    cell_types = [_sanitize(ct) for ct in cell_types_raw[:5]]
    if not cell_types:
        cell_types = ["Cell_A"]

    # Adhesion matrix
    adhesion_energies = params.get("adhesion_energies", {})
    adhesion_matrix: dict[str, float] = {}
    for key, val in adhesion_energies.items():
        adhesion_matrix[key] = max(0, min(200, _extract_val(val)))
    if not adhesion_matrix:
        for ct in cell_types:
            adhesion_matrix[f"Medium_{ct}"] = 16
            adhesion_matrix[f"Scaffold_{ct}"] = 5
            adhesion_matrix[f"{ct}_{ct}"] = 2
        for i, ct1 in enumerate(cell_types):
            for ct2 in cell_types[i + 1:]:
                adhesion_matrix[f"{ct1}_{ct2}"] = 11
        adhesion_matrix["Medium_Scaffold"] = 20
        adhesion_matrix["Medium_Medium"] = 0

    # Volume / surface constraints
    vol = params.get("volume_constraints", {"target_volume": 100, "lambda_volume": 2})
    surf = params.get("surface_constraints", {"target_surface": 80, "lambda_surface": 1})
    target_vol = max(10, min(1000, vol.get("target_volume", 100)))
    lambda_vol = max(0.5, min(20, vol.get("lambda_volume", 2)))
    target_surf = max(10, min(500, surf.get("target_surface", 80)))
    lambda_surf = max(0.1, min(10, surf.get("lambda_surface", 1)))

    # O2 diffusion parameters
    diff_params = params.get("diffusion_parameters", {}).get("o2", {})
    has_o2 = bool(diff_params)
    o2_diffusion = float(diff_params.get("D", 2.0e-5))
    o2_decay = float(diff_params.get("decay", 0.0))
    o2_consumption = float(diff_params.get("consumption_rate", 0.01))
    o2_boundary = float(diff_params.get("boundary_concentration", 0.2))

    # Proliferation parameters
    prolif = params.get("proliferation_parameters", {})
    doubling_time_h = float(prolif.get("doubling_time_hours", 0))
    mcs_per_hour = max_steps / max(float(params.get("culture_duration_hours", 168)), 1)
    doubling_time_mcs = doubling_time_h * mcs_per_hour if doubling_time_h > 0 else 0
    ci_neighbors = int(prolif.get("contact_inhibition_neighbors", 8))

    # Scaffold parameters
    scaffold_params = params.get("scaffold_parameters", {})
    scaffold_type = scaffold_params.get("type", "rigid")
    ecm_deg_rate = float(scaffold_params.get("ecm_degradation_rate", 0.0))
    has_ecm_field = scaffold_type in ("degradable", "hybrid")

    # Boundary conditions
    bc = params.get("boundary_conditions", {})
    pbc_axes = [a for a in ("x", "y", "z") if bc.get(f"periodic_{a}", False)]
    if not pbc_axes and bc.get("all_periodic", False):
        pbc_axes = ["x", "y", "z"]

    # Culture protocol — media changes
    protocol = params.get("culture_protocol", {})
    media_interval_h = float(protocol.get("media_change_interval_hours", 0))
    culture_duration_h = float(params.get("culture_duration_hours", 168))
    media_change_mcs: list[int] = []
    if media_interval_h > 0 and mcs_per_hour > 0:
        t = media_interval_h
        while t < culture_duration_h:
            media_change_mcs.append(int(t * mcs_per_hour))
            t += media_interval_h

    # Lattice dimensions
    dims = (100, 100, 100)
    dim_spec = params.get("lattice_dimensions")
    if dim_spec and len(dim_spec) == 3:
        dims = (int(dim_spec[0]), int(dim_spec[1]), int(dim_spec[2]))

    max_steps = max(100, min(50000, max_steps))
    output_frequency = max(1, min(max_steps, output_frequency))

    # Generate PIF if not provided
    if pif_content is None:
        pif_content = ""

    steppable_py = _generate_steppable_py(
        cell_types=cell_types,
        target_vol=target_vol,
        lambda_vol=lambda_vol,
        target_surf=target_surf,
        lambda_surf=lambda_surf,
        mcs_steps=max_steps,
        vtk_output_freq=output_frequency,
        has_o2=has_o2,
        o2_consumption_rate=o2_consumption,
        o2_boundary_value=o2_boundary,
        doubling_time_mcs=doubling_time_mcs,
        contact_inhibition_neighbors=ci_neighbors,
        media_change_mcs=media_change_mcs,
        scaffold_type=scaffold_type,
        ecm_degradation_rate=ecm_deg_rate,
        dims=dims,
    )

    project_xml = _generate_project_xml(
        dims=dims,
        cell_types=cell_types,
        adhesion_matrix=adhesion_matrix,
        mcs_steps=max_steps,
        pbc_axes=pbc_axes,
        has_o2=has_o2,
        o2_diffusion=o2_diffusion,
        o2_decay=o2_decay,
        o2_boundary=o2_boundary,
        has_ecm_field=has_ecm_field,
        has_pif=bool(pif_content),
    )

    return steppable_py, project_xml, pif_content


# Keep backward compat alias
def generate_cc3d_script(brief: dict, max_steps: int = 1000, output_frequency: int = 100) -> str:
    """Backward-compatible wrapper that returns only the steppable script."""
    py, _, _ = generate_cc3d_project(brief, max_steps, output_frequency)
    return py


# ---------------------------------------------------------------------------
# Execution and VTK collection (unchanged)
# ---------------------------------------------------------------------------

async def execute_cc3d(
    cc3d_python: str,
    script_path: Path,
    output_dir: Path,
    timeout: int = 120,
    output_frequency: int = 100,
):
    """Execute CC3D script headlessly, capture output."""
    try:
        proc = await asyncio.create_subprocess_exec(
            cc3d_python, "-m", "cc3d.run_script",
            "-i", str(script_path),
            "-o", str(output_dir),
            "-f", str(output_frequency),
            "--current-dir", str(output_dir),
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
    """Find VTK files (cell field + scalar fields), encode as base64."""
    vtk_files = sorted(job_dir.rglob("*.vtk"))
    frames = []
    for vtk_path in vtk_files[:20]:
        content = vtk_path.read_bytes()
        frames.append({
            "filename": vtk_path.name,
            "data_b64": base64.b64encode(content).decode(),
            "size_bytes": len(content),
            "field_type": "o2" if "O2" in vtk_path.name else "cell",
        })
    return frames
