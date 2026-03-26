"""
core/ooc_physics.py

Organ-on-Chip (OoC) physics models.

Wall shear stress for rectangular microchannels:
    tau = 6 * mu * Q / (w * h^2)

Where:
    tau = wall shear stress (Pa)
    mu  = dynamic viscosity (Pa*s)
    Q   = volumetric flow rate (m^3/s)
    w   = channel width (m)
    h   = channel height (m)

References:
    Bhatia & Ingber Nat Biotechnol 2014 doi:10.1038/nbt.2989
    Huh et al. Science 2010 doi:10.1126/science.1188302
"""

import math


# TEER calibration curves from literature
# {cell_type: [(shear_dyn_cm2, culture_days, teer_ohm_cm2, teer_sd)]}
OOC_TEER_CURVES = {
    "caco2": [
        (0.0, 7, 150.0, 25.0),
        (0.5, 7, 280.0, 40.0),
        (1.0, 7, 420.0, 55.0),
        (2.0, 7, 580.0, 70.0),
        (0.0, 14, 320.0, 35.0),
        (0.5, 14, 550.0, 60.0),
        (1.0, 14, 750.0, 80.0),
        (2.0, 14, 920.0, 95.0),
        (0.0, 21, 450.0, 50.0),
        (0.5, 21, 680.0, 70.0),
        (1.0, 21, 900.0, 90.0),
        (2.0, 21, 1100.0, 110.0),
    ],
    "huvec": [
        (0.5, 3, 50.0, 10.0),
        (1.0, 3, 65.0, 12.0),
        (5.0, 3, 85.0, 15.0),
        (10.0, 3, 95.0, 18.0),
        (0.5, 7, 70.0, 12.0),
        (1.0, 7, 90.0, 15.0),
        (5.0, 7, 120.0, 20.0),
        (10.0, 7, 140.0, 25.0),
    ],
    "primary_hepatocytes": [
        (0.0, 3, 80.0, 15.0),
        (0.1, 3, 100.0, 18.0),
        (0.5, 3, 130.0, 22.0),
        (1.0, 3, 110.0, 20.0),
        (0.0, 7, 120.0, 20.0),
        (0.1, 7, 160.0, 25.0),
        (0.5, 7, 210.0, 30.0),
        (1.0, 7, 180.0, 28.0),
    ],
}


def predict_wall_shear_stress(
    flow_rate_ul_min: float,
    channel_width_um: float,
    channel_height_um: float,
    viscosity_pas: float = 0.001,
) -> float:
    """
    Calculate wall shear stress in a rectangular microchannel.

    tau = 6 * mu * Q / (w * h^2)

    Args:
        flow_rate_ul_min: Volumetric flow rate in uL/min
        channel_width_um: Channel width in micrometers
        channel_height_um: Channel height in micrometers
        viscosity_pas: Dynamic viscosity in Pa*s (default: water at 37C)

    Returns:
        Wall shear stress in dyn/cm^2 (1 Pa = 10 dyn/cm^2)
    """
    # Convert units to SI
    Q_m3s = flow_rate_ul_min * 1e-9 / 60.0  # uL/min -> m^3/s
    w_m = channel_width_um * 1e-6  # um -> m
    h_m = channel_height_um * 1e-6  # um -> m

    # Wall shear stress in Pa
    tau_pa = 6.0 * viscosity_pas * Q_m3s / (w_m * h_m * h_m)

    # Convert to dyn/cm^2 (1 Pa = 10 dyn/cm^2)
    tau_dyn_cm2 = tau_pa * 10.0

    return tau_dyn_cm2


def predict_teer(
    cell_type: str,
    shear_dyn_cm2: float,
    culture_days: int,
) -> tuple:
    """
    Predict TEER (transepithelial/transendothelial electrical resistance)
    from cell type, shear stress, and culture duration.

    Uses calibrated data from literature with manual linear interpolation.

    Args:
        cell_type: One of "caco2", "huvec", "primary_hepatocytes"
        shear_dyn_cm2: Applied wall shear stress in dyn/cm^2
        culture_days: Days in culture

    Returns:
        (teer_ohm_cm2, sd) — predicted TEER and standard deviation
    """
    cell_key = cell_type.lower().replace(" ", "_").replace("-", "_")
    if cell_key not in OOC_TEER_CURVES:
        raise ValueError(
            f"Unknown cell type '{cell_type}'. "
            f"Available: {list(OOC_TEER_CURVES.keys())}"
        )

    curve = OOC_TEER_CURVES[cell_key]

    # Get available culture day timepoints
    available_days = sorted(set(pt[1] for pt in curve))

    # Find bracketing days for interpolation
    if culture_days <= available_days[0]:
        day_lo = day_hi = available_days[0]
    elif culture_days >= available_days[-1]:
        day_lo = day_hi = available_days[-1]
    else:
        day_lo = available_days[0]
        day_hi = available_days[-1]
        for d in available_days:
            if d <= culture_days:
                day_lo = d
            if d >= culture_days and day_hi >= d:
                day_hi = d

    def _interp_at_day(day: int) -> tuple:
        """Interpolate TEER at a given day across shear values."""
        pts = [(pt[0], pt[2], pt[3]) for pt in curve if pt[1] == day]
        pts.sort(key=lambda x: x[0])

        if not pts:
            return 200.0, 50.0  # fallback

        shears = [p[0] for p in pts]
        teers = [p[1] for p in pts]
        sds = [p[2] for p in pts]

        if shear_dyn_cm2 <= shears[0]:
            return teers[0], sds[0]
        if shear_dyn_cm2 >= shears[-1]:
            return teers[-1], sds[-1]

        for i in range(len(shears) - 1):
            if shears[i] <= shear_dyn_cm2 <= shears[i + 1]:
                t = (shear_dyn_cm2 - shears[i]) / (shears[i + 1] - shears[i])
                teer = teers[i] + t * (teers[i + 1] - teers[i])
                sd = sds[i] + t * (sds[i + 1] - sds[i])
                return teer, sd

        return teers[-1], sds[-1]

    teer_lo, sd_lo = _interp_at_day(day_lo)

    if day_lo == day_hi:
        return round(teer_lo, 1), round(sd_lo, 1)

    teer_hi, sd_hi = _interp_at_day(day_hi)
    t = (culture_days - day_lo) / (day_hi - day_lo)
    teer = teer_lo + t * (teer_hi - teer_lo)
    sd = sd_lo + t * (sd_hi - sd_lo)

    return round(teer, 1), round(sd, 1)
