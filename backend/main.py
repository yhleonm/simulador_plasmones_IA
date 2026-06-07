from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
from typing import List
import os

from backend.models.schemas import SimulationRequest, SimulationWithAngleRequest, ReflectanceResponse, FieldProfileResponse, OptimizationRequest, OptimizationResponse, Simulation2DRequest, Simulation2DResponse, KineticsRequest, KineticsResponse, XAIRequest, XAIResponse
from backend.core.engine import calculate_tmm, calculate_field_profile, get_available_materials, parse_refractive_index_csv, DB_PATH, get_refractive_index
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

def classify_sensor_mode(layers: List[dict], wavelength_nm: float, polarization: str) -> str:
    has_metal = False
    metal_thickness = 0.0
    has_lossy_dielectric = False
    has_transparent_dielectric = False
    
    for idx, L in enumerate(layers):
        if idx == 0 or idx == len(layers) - 1:
            continue
            
        material = L.get('material', '')
        if material == 'Grafeno':
            continue
            
        try:
            n_c = get_refractive_index(L, wavelength_nm)
            eps = n_c ** 2
            re_eps = eps.real
            im_eps = eps.imag
            
            d = L.get('d', 0.0)
            
            if re_eps < 0 and n_c.imag > 1.0:
                has_metal = True
                metal_thickness += d
            elif re_eps > 0 and n_c.imag > 0.05 and d > 10.0:
                has_lossy_dielectric = True
            elif re_eps > 0 and n_c.imag <= 0.05 and d > 10.0:
                has_transparent_dielectric = True
        except Exception:
            pass

    if has_metal and has_lossy_dielectric:
        return "Resonancia Hibrida (SPR + LMR)"
        
    if has_metal:
        if polarization == 'TE':
            return "Modo Metalico (Sin plasmon en TE)"
        if metal_thickness < 30.0 and len(layers) >= 4:
            return "LR-SPR (Plasmon de Largo Alcance)"
        if has_transparent_dielectric:
            return "WC-SPR (Plasmon Acoplado a Guia de Onda)"
        return "SPR (Resonancia de Plasmon Superficial)"
        
    if has_lossy_dielectric:
        return "LMR (Resonancia en Modo de Perdidas)"
        
    if has_transparent_dielectric:
        return "Guia de Onda Dielectrica (WG)"
        
    return "Dielectrico Simple / No resonante"

@app.post("/api/simulate/reflectance", response_model=ReflectanceResponse)
def simulate_reflectance(req: SimulationRequest):
    print(f"DEBUG: Received reflectance request for {len(req.layers)} layers")
    layers = [layer.model_dump() for layer in req.layers]
    sensor_mode = classify_sensor_mode(layers, req.wavelength_nm, req.polarization)
    
    if req.interrogation_mode == "spectral":
        wls = np.linspace(400, 1000, 600)
        R_vals = []
        phase_tm = []
        phase_te = []
        phase_diff = []
        fixed_angle = req.fixed_angle_deg if req.fixed_angle_deg is not None else 45.0
        
        try:
            for wl in wls:
                R_tm, _, r_tm = calculate_tmm(wl, fixed_angle, layers, 'TM', return_coefficient=True)
                R_te, _, r_te = calculate_tmm(wl, fixed_angle, layers, 'TE', return_coefficient=True)
                
                # Reflectance for the selected polarization
                R = R_tm if req.polarization == 'TM' else R_te
                R_vals.append(float(R))
                
                # Phase calculation (argument in radians)
                phi_tm = np.angle(r_tm)
                phi_te = np.angle(r_te)
                diff = phi_tm - phi_te
                # Wrap to [-pi, pi]
                diff = np.arctan2(np.sin(diff), np.cos(diff))
                
                phase_tm.append(float(phi_tm))
                phase_te.append(float(phi_te))
                phase_diff.append(float(diff))
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
            fom=0.0,
            sensor_mode=sensor_mode,
            phase_tm=phase_tm,
            phase_te=phase_te,
            phase_diff=phase_diff
        )
    else:
        angles = np.linspace(30, 85, 800)
        R_vals = []
        phase_tm = []
        phase_te = []
        phase_diff = []
        
        try:
            for theta in angles:
                R_tm, _, r_tm = calculate_tmm(req.wavelength_nm, theta, layers, 'TM', return_coefficient=True)
                R_te, _, r_te = calculate_tmm(req.wavelength_nm, theta, layers, 'TE', return_coefficient=True)
                
                # Reflectance for the selected polarization
                R = R_tm if req.polarization == 'TM' else R_te
                R_vals.append(float(R))
                
                # Phase calculation (argument in radians)
                phi_tm = np.angle(r_tm)
                phi_te = np.angle(r_te)
                diff = phi_tm - phi_te
                # Wrap to [-pi, pi]
                diff = np.arctan2(np.sin(diff), np.cos(diff))
                
                phase_tm.append(float(phi_tm))
                phase_te.append(float(phi_te))
                phase_diff.append(float(diff))
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
            fom=0.0,
            sensor_mode=sensor_mode,
            phase_tm=phase_tm,
            phase_te=phase_te,
            phase_diff=phase_diff
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
    
    # Analytical penetration depth L calculation
    try:
        n_prisma = get_refractive_index(layers[0], req.wavelength_nm)
        n_analito = get_refractive_index(layers[-1], req.wavelength_nm)
        
        theta_rad = np.radians(req.theta_deg)
        eps_analito = n_analito ** 2
        
        term = eps_analito - (n_prisma * np.sin(theta_rad)) ** 2
        sqrt_term = np.lib.scimath.sqrt(term)
        im_part = np.abs(np.imag(sqrt_term))
        
        if im_part > 1e-9:
            penetration_depth = float(req.wavelength_nm / (2 * np.pi * im_part))
        else:
            penetration_depth = None
    except Exception as e:
        print(f"Error calculating penetration depth: {e}")
        penetration_depth = None
        
    return FieldProfileResponse(
        z=z.tolist(),
        E_sq=E_sq.tolist(),
        layer_bounds=bounds,
        materials=materials,
        penetration_depth=penetration_depth
    )

@app.post("/api/optimize", response_model=OptimizationResponse)
def optimize_structure(req: OptimizationRequest):
    target = req.target if req.target is not None else "Minimizar Reflectancia"
    wl = req.wavelength_nm
    pol = req.polarization

    def objective(d_values):
        temp_layers = [L.model_dump() for L in req.layers]
        for i, idx in enumerate(req.optimize_indices):
            temp_layers[idx]['d'] = d_values[i]
        
        # Fast angular scan to find resonance curve
        angles_opt = np.linspace(35, 80, 300)
        rs = []
        for th in angles_opt:
            R, _ = calculate_tmm(wl, th, temp_layers, pol)
            rs.append(R)
        rs = np.array(rs)
        
        min_R = np.min(rs)
        min_idx = np.argmin(rs)
        res_angle = angles_opt[min_idx]
        
        # Calculate FWHM
        half_max = (1.0 + min_R) / 2.0
        left_side = np.where(rs[:min_idx] > half_max)[0]
        right_side = np.where(rs[min_idx:] > half_max)[0]
        izq = left_side[-1] if len(left_side) > 0 else 0
        der = right_side[0] + min_idx if len(right_side) > 0 else len(rs) - 1
        fwhm = angles_opt[der] - angles_opt[izq]
        
        if target == "Minimizar Reflectancia":
            alpha = 0.05
            costo_final = min_R + (alpha * fwhm)
            if fwhm > 15.0:
                costo_final += 10.0
            return float(costo_final)
        else:
            # Perturb the last layer for Sensitivity/FoM calculations
            temp_layers_perturbed = [L.copy() for L in temp_layers]
            n_base_complex = get_refractive_index(temp_layers[-1], wl)
            n_base = n_base_complex.real
            k_base = n_base_complex.imag
            
            temp_layers_perturbed[-1] = {
                "material": "Personalizado (Manual)",
                "d": 0.0,
                "custom_n": n_base + 0.005,
                "custom_k": k_base
            }
            
            rs_pert = []
            for th in angles_opt:
                R_pert, _ = calculate_tmm(wl, th, temp_layers_perturbed, pol)
                rs_pert.append(R_pert)
            rs_pert = np.array(rs_pert)
            
            min_idx_pert = np.argmin(rs_pert)
            res_angle_pert = angles_opt[min_idx_pert]
            
            shift = abs(res_angle_pert - res_angle)
            sens = shift / 0.005  # S = shift / delta_n
            
            if min_R > 0.3 or fwhm < 0.1 or fwhm > 15.0:
                return float(1000.0 + min_R * 100.0)
                
            if target == "Maximizar Sensibilidad":
                return float(-sens + 5.0 * min_R)
            elif target == "Maximizar FoM":
                fom = sens / fwhm if fwhm > 0 else 0.0
                return float(-fom + 5.0 * min_R)
            
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
        
    # Calculate actual min reflectance of optimized configuration
    optimized_layers_dump = [L.model_dump() for L in optimized_layers]
    angles = np.linspace(35, 80, 300)
    actual_min_R = 1.0
    for th in angles:
        R, _ = calculate_tmm(req.wavelength_nm, th, optimized_layers_dump, req.polarization)
        if R < actual_min_R: actual_min_R = R
        
    return OptimizationResponse(
        optimized_layers=optimized_layers,
        min_reflectance=float(actual_min_R)
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

@app.post("/api/analyze/xai", response_model=XAIResponse)
def analyze_xai(req: XAIRequest):
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    
    V = len(req.analyze_indices)
    if V == 0:
        raise HTTPException(status_code=400, detail="Debes seleccionar al menos una capa para analizar.")
        
    N = max(200, 50 * V)
    original_layers = [L.model_dump() for L in req.layers]
    
    def find_resonance(layers_config):
        if req.interrogation_mode == "spectral":
            wavelengths = np.linspace(400, 1000, 200)
            fixed_angle = req.fixed_angle_deg if req.fixed_angle_deg is not None else 45.0
            r_vals = []
            for wl in wavelengths:
                r, _ = calculate_tmm(wl, fixed_angle, layers_config, req.polarization)
                r_vals.append(r)
            return float(wavelengths[np.argmin(r_vals)])
        else:
            angles = np.linspace(30, 85, 300)
            r_vals = []
            for th in angles:
                r, _ = calculate_tmm(req.wavelength_nm, th, layers_config, req.polarization)
                r_vals.append(r)
            return float(angles[np.argmin(r_vals)])
            
    X_samples = []
    y_resonance = []
    
    for i in range(N):
        temp_layers = [dict(L) for L in original_layers]
        sample_row = []
        for idx_in_list, layer_idx in enumerate(req.analyze_indices):
            b_min = req.bounds_min[idx_in_list]
            b_max = req.bounds_max[idx_in_list]
            val = np.random.uniform(b_min, b_max)
            temp_layers[layer_idx]['d'] = val
            sample_row.append(val)
            
        try:
            res = find_resonance(temp_layers)
            X_samples.append(sample_row)
            y_resonance.append(res)
        except Exception:
            continue
            
    if len(X_samples) < 10:
        raise HTTPException(status_code=500, detail="Error generando suficientes muestras validas para entrenar la IA.")
        
    X_array = np.array(X_samples)
    y_array = np.array(y_resonance)
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_array)
    
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_scaled, y_array)
    
    importances = model.feature_importances_.tolist()
    
    variables_data = []
    for idx_in_list, layer_idx in enumerate(req.analyze_indices):
        b_min = req.bounds_min[idx_in_list]
        b_max = req.bounds_max[idx_in_list]
        
        sweep_grid = np.linspace(b_min, b_max, 25)
        sweep_points = []
        
        for val in sweep_grid:
            temp_layers = [dict(L) for L in original_layers]
            temp_layers[layer_idx]['d'] = val
            try:
                res = find_resonance(temp_layers)
                sweep_points.append({
                    "value": float(val),
                    "resonance": float(res)
                })
            except Exception:
                pass
                
        variables_data.append({
            "layer_index": int(layer_idx),
            "material": original_layers[layer_idx]['material'],
            "importance": float(importances[idx_in_list]),
            "sweep": sweep_points
        })
        
    return {"variables": variables_data}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

