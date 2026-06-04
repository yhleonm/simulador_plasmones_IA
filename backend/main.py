from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
from typing import List
import os

from backend.models.schemas import SimulationRequest, SimulationWithAngleRequest, ReflectanceResponse, FieldProfileResponse, OptimizationRequest, OptimizationResponse, Simulation2DRequest, Simulation2DResponse, KineticsRequest, KineticsResponse
from backend.core.engine import calculate_tmm, calculate_field_profile, get_available_materials, parse_refractive_index_csv, DB_PATH
from scipy.optimize import differential_evolution

app = FastAPI(title="SPR Simulator API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "SPR Simulator API is running"}

@app.get("/api/materials")
def list_materials():
    try:
        return get_available_materials()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/materials/import")
def import_material(file: UploadFile = File(...), name: str = Form(...)):
    if not name.strip():
        raise HTTPException(status_code=400, detail="El nombre del material no puede estar vacío.")
    
    try:
        content_bytes = file.file.read()
        content_str = content_bytes.decode("utf-8", errors="ignore")
        
        # Parse RefractiveIndex.info CSV
        df = parse_refractive_index_csv(content_str)
        
        # Sanitize name to make safe filename
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-', '(', ')')).strip()
        safe_filename = safe_name.replace(" ", "_") + ".csv"
        
        # Ensure database folder exists
        os.makedirs(DB_PATH, exist_ok=True)
        
        # Save CSV file
        dest_path = os.path.join(DB_PATH, safe_filename)
        df.to_csv(dest_path, index=False)
        
        # Clear lru cache
        from backend.core.engine import get_interpolator
        get_interpolator.cache_clear()
        
        return {
            "status": "success", 
            "message": f"Material '{name}' importado correctamente como '{safe_filename}'", 
            "filename": safe_filename
        }
    except Exception as e:
        print(f"Error importando material: {e}")
        raise HTTPException(status_code=400, detail=f"Error parseando CSV: {str(e)}")

@app.post("/api/simulate/reflectance", response_model=ReflectanceResponse)
def simulate_reflectance(req: SimulationRequest):
    print(f"DEBUG: Received reflectance request for {len(req.layers)} layers")
    layers = [layer.model_dump() for layer in req.layers]
    
    if req.interrogation_mode == "spectral":
        wls = np.linspace(400, 1000, 600)
        R_vals = []
        fixed_angle = req.fixed_angle_deg if req.fixed_angle_deg is not None else 45.0
        
        try:
            for wl in wls:
                R, _ = calculate_tmm(wl, fixed_angle, layers, req.polarization)
                R_vals.append(float(R))
        except Exception as e:
            print(f"ERROR in spectral TMM calculation: {e}")
            raise e
            
        min_idx = np.argmin(R_vals)
        res_wl = float(wls[min_idx])
        min_R = float(R_vals[min_idx])
        
        from backend.core.engine import calculate_fwhm
        fwhm = calculate_fwhm(wls, R_vals, res_wl)
        
        return ReflectanceResponse(
            wavelengths=wls.tolist(),
            reflectance=R_vals,
            resonance_wavelength=res_wl,
            min_reflectance=min_R,
            fwhm=float(fwhm),
            fom=0.0
        )
    else:
        angles = np.linspace(30, 85, 800)
        R_vals = []
        
        try:
            for theta in angles:
                R, _ = calculate_tmm(req.wavelength_nm, theta, layers, req.polarization)
                R_vals.append(float(R))
        except Exception as e:
            print(f"ERROR in angular TMM calculation: {e}")
            raise e
        
        min_idx = np.argmin(R_vals)
        res_angle = float(angles[min_idx])
        min_R = float(R_vals[min_idx])
        
        # Calculate FWHM
        from backend.core.engine import calculate_fwhm
        fwhm = calculate_fwhm(angles, R_vals, res_angle)
        
        return ReflectanceResponse(
            angles=angles.tolist(),
            reflectance=R_vals,
            resonance_angle=res_angle,
            min_reflectance=min_R,
            fwhm=float(fwhm),
            fom=0.0
        )


@app.post("/api/simulate/field", response_model=FieldProfileResponse)
def simulate_field(req: SimulationWithAngleRequest):
    layers = [layer.model_dump() for layer in req.layers]
    
    z, E_sq = calculate_field_profile(
        req.wavelength_nm, req.theta_deg, layers, req.polarization
    )
    
    # Calculate layer boundaries and collect materials
    bounds = [0.0]
    current = 0.0
    materials = [req.layers[0].material]
    for L in req.layers[1:-1]:
        current += L.d
        bounds.append(current)
        materials.append(L.material)
    materials.append(req.layers[-1].material)
    
    return FieldProfileResponse(
        z=z.tolist(),
        E_sq=E_sq.tolist(),
        layer_bounds=bounds,
        materials=materials
    )

@app.post("/api/optimize", response_model=OptimizationResponse)
def optimize_structure(req: OptimizationRequest):
    def objective(d_values):
        temp_layers = [L.model_dump() for L in req.layers]
        for i, idx in enumerate(req.optimize_indices):
            temp_layers[idx]['d'] = d_values[i]
        
        # Fast angular scan to find min R
        angles = np.linspace(35, 80, 200)
        min_R = 1.0
        for th in angles:
            R, _ = calculate_tmm(req.wavelength_nm, th, temp_layers, req.polarization)
            if R < min_R: min_R = R
        return float(min_R)

    bounds = []
    for i in range(len(req.optimize_indices)):
        b_min = req.bounds_min[i] if (req.bounds_min is not None and i < len(req.bounds_min)) else 20.0
        b_max = req.bounds_max[i] if (req.bounds_max is not None and i < len(req.bounds_max)) else 90.0
        bounds.append((b_min, b_max))
        
    result = differential_evolution(objective, bounds, seed=42, maxiter=30, popsize=10)
    
    optimized_layers = [L.model_copy() for L in req.layers]
    for i, idx in enumerate(req.optimize_indices):
        optimized_layers[idx].d = float(result.x[i])
        
    return OptimizationResponse(
        optimized_layers=optimized_layers,
        min_reflectance=float(result.fun)
    )

@app.post("/api/simulate/reflectance-2d", response_model=Simulation2DResponse)
def simulate_reflectance_2d(req: Simulation2DRequest):
    layers = [layer.model_dump() for layer in req.layers]
    
    angles = np.linspace(req.angle_min, req.angle_max, req.angle_steps).tolist()
    wavelengths = np.linspace(req.wl_min, req.wl_max, req.wl_steps).tolist()
    
    matrix = []
    try:
        for wl in wavelengths:
            row = []
            for theta in angles:
                R, _ = calculate_tmm(wl, theta, layers, req.polarization)
                row.append(float(R))
            matrix.append(row)
    except Exception as e:
        print(f"ERROR in 2D TMM calculation: {e}")
        raise e
        
    return Simulation2DResponse(
        angles=angles,
        wavelengths=wavelengths,
        matrix=matrix
    )

@app.post("/api/simulate/kinetics", response_model=KineticsResponse)
def simulate_kinetics(req: KineticsRequest):
    # Determine the time grid (e.g., 100 points for a smooth and fast plot)
    t_vals = np.linspace(0, req.t_total, 120)
    
    # Precalculate Langmuir kinetics
    ka = req.ka
    kd = req.kd
    c = req.concentration
    t_assoc = req.t_assoc
    
    eq_ratio = (ka * c) / (ka * c + kd) if (ka * c + kd) > 0 else 0.0
    rate = ka * c + kd
    theta_assoc = eq_ratio * (1.0 - np.exp(-rate * t_assoc))
    
    original_layers = [L.model_dump() for L in req.layers]
    
    # Helper to find resonance with full scan
    def find_resonance_full(layers_config):
        if req.interrogation_mode == "spectral":
            wavelengths = np.linspace(400, 1000, 400)
            fixed_angle = req.fixed_angle_deg if req.fixed_angle_deg is not None else 45.0
            r_vals = []
            for wl in wavelengths:
                r, _ = calculate_tmm(wl, fixed_angle, layers_config, req.polarization)
                r_vals.append(r)
            return float(wavelengths[np.argmin(r_vals)])
        else:
            angles = np.linspace(30, 85, 550)
            r_vals = []
            for th in angles:
                r, _ = calculate_tmm(req.wavelength_nm, th, layers_config, req.polarization)
                r_vals.append(r)
            return float(angles[np.argmin(r_vals)])

    # Helper to find resonance with narrow scan for speed and precision
    def find_resonance_narrow(layers_config, baseline_val):
        if req.interrogation_mode == "spectral":
            wl_min = max(400.0, baseline_val - 15.0)
            wl_max = min(1000.0, baseline_val + 85.0)
            wavelengths = np.linspace(wl_min, wl_max, 150)
            fixed_angle = req.fixed_angle_deg if req.fixed_angle_deg is not None else 45.0
            r_vals = []
            for wl in wavelengths:
                r, _ = calculate_tmm(wl, fixed_angle, layers_config, req.polarization)
                r_vals.append(r)
            return float(wavelengths[np.argmin(r_vals)])
        else:
            th_min = max(30.0, baseline_val - 1.5)
            th_max = min(89.0, baseline_val + 6.0)
            angles = np.linspace(th_min, th_max, 150)
            r_vals = []
            for theta in angles:
                r, _ = calculate_tmm(req.wavelength_nm, theta, layers_config, req.polarization)
                r_vals.append(r)
            return float(angles[np.argmin(r_vals)])

    # 1. Calculate baseline resonance (at t=0, adlayer thickness = 0)
    try:
        baseline = find_resonance_full(original_layers)
    except Exception as e:
        print(f"Error calculating baseline resonance: {e}")
        raise HTTPException(status_code=500, detail=f"Error al calcular la resonancia base: {str(e)}")
        
    points = []
    
    # 2. Run simulation over time
    for t in t_vals:
        # Calculate coverage ratio using analytical Langmuir equation
        if t <= t_assoc:
            ratio = eq_ratio * (1.0 - np.exp(-rate * t))
        else:
            ratio = theta_assoc * np.exp(-kd * (t - t_assoc))
            
        # Adlayer thickness is proportional to coverage
        d_adlayer = req.d_max * ratio
        
        # Build layer structure by inserting biological adlayer right before the last layer
        sim_layers = list(original_layers)
        adlayer = {
            "material": "Personalizado (Manual)",
            "d": d_adlayer,
            "custom_n": req.n_adlayer,
            "custom_k": 0.0
        }
        sim_layers.insert(len(sim_layers) - 1, adlayer)
        
        # Calculate resonance for this time step (using the fast narrow window around baseline)
        try:
            res_val = find_resonance_narrow(sim_layers, baseline)
            shift = res_val - baseline
            points.append({
                "time": float(t),
                "shift": float(shift),
                "resonance": float(res_val)
            })
        except Exception as e:
            print(f"Error calculating resonance at t={t}: {e}")
            points.append({
                "time": float(t),
                "shift": 0.0,
                "resonance": baseline
            })
            
    unit = "nm" if req.interrogation_mode == "spectral" else "deg"
    return {
        "points": points,
        "unit": unit
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

