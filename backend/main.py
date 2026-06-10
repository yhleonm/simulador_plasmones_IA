from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
from typing import List
import os

from backend.models.schemas import (
    SimulationRequest, SimulationWithAngleRequest, ReflectanceResponse, 
    FieldProfileResponse, OptimizationRequest, OptimizationResponse, 
    Simulation2DRequest, Simulation2DResponse, KineticsRequest, 
    KineticsResponse, XAIRequest, XAIResponse, CurveFitRequest, 
    CurveFitResponse, FitParameterConfig, ThermalSweepResponse, 
    ThermalSweepCurve, CalibrationRequest, CalibrationResponse,
    MonteCarloRequest, MonteCarloResponse, MonteCarloStats, LayerPerturbation,
    PhaseSensitivityRequest, PhaseSensitivityResponse,
    LRSPPSweepRequest, LRSPPSweepResponse
)
from backend.core.engine import calculate_tmm, calculate_field_profile, get_available_materials, parse_refractive_index_csv, DB_PATH, get_refractive_index
from scipy.optimize import differential_evolution, minimize

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

from pydantic import BaseModel

class MaterialImportUrlRequest(BaseModel):
    url: str

@app.post("/api/materials/import-url")
def import_material_url(req: MaterialImportUrlRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="La URL no puede estar vacía.")
    
    try:
        from backend.core.engine import import_material_from_url, get_interpolator
        result = import_material_from_url(url)
        
        # Clear engine cache
        get_interpolator.cache_clear()
        
        return {
            "status": "success",
            "message": f"Material '{result['display_name']}' importado correctamente.",
            "filename": result['filename'],
            "display_name": result['display_name']
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error importando material por URL: {e}")
        raise HTTPException(status_code=500, detail=f"Error al procesar el material: {str(e)}")

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

def add_gaussian_noise(signal: List[float], snr_db: float, is_phase: bool = False) -> List[float]:
    if snr_db is None or snr_db <= 0:
        return None
    arr = np.array(signal)
    if is_phase:
        std = np.pi * (10.0 ** (-snr_db / 20.0))
        noise = np.random.normal(0, std, size=arr.shape)
        noisy_arr = arr + noise
        noisy_arr = np.arctan2(np.sin(noisy_arr), np.cos(noisy_arr))
    else:
        std = 10.0 ** (-snr_db / 20.0)
        noise = np.random.normal(0, std, size=arr.shape)
        noisy_arr = np.clip(arr + noise, 0.0, 1.0)
    return noisy_arr.tolist()

@app.post("/api/simulate/reflectance", response_model=ReflectanceResponse)
def simulate_reflectance(req: SimulationRequest):
    print(f"DEBUG: Received reflectance request for {len(req.layers)} layers")
    layers = [layer.model_dump() for layer in req.layers]
    sensor_mode = classify_sensor_mode(layers, req.wavelength_nm, req.polarization)
    
    if req.interrogation_mode == "spectral":
        wls = np.linspace(400, 1000, 300)
        R_vals = []
        T_vals = []
        phase_tm = []
        phase_te = []
        phase_diff = []
        fixed_angle = req.fixed_angle_deg if req.fixed_angle_deg is not None else 45.0
        
        try:
            for wl in wls:
                R_tm, T_tm, r_tm = calculate_tmm(wl, fixed_angle, layers, 'TM', return_coefficient=True, temperature_c=req.temperature_c)
                R_te, T_te, r_te = calculate_tmm(wl, fixed_angle, layers, 'TE', return_coefficient=True, temperature_c=req.temperature_c)
                
                R = R_tm if req.polarization == 'TM' else R_te
                R_vals.append(float(R))
                
                T = T_tm if req.polarization == 'TM' else T_te
                T_vals.append(float(T))
                
                phi_tm = np.angle(r_tm)
                phi_te = np.angle(r_te)
                diff = phi_tm - phi_te
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
        
        R_vals_noisy = None
        T_vals_noisy = None
        phase_diff_noisy = None
        if req.snr_db is not None:
            R_vals_noisy = add_gaussian_noise(R_vals, req.snr_db, is_phase=False)
            T_vals_noisy = add_gaussian_noise(T_vals, req.snr_db, is_phase=False)
            phase_diff_noisy = add_gaussian_noise(phase_diff, req.snr_db, is_phase=True)
        
        return ReflectanceResponse(
            wavelengths=wls.tolist(),
            reflectance=R_vals,
            transmittance=T_vals,
            resonance_wavelength=res_wl,
            min_reflectance=min_R,
            fwhm=float(fwhm),
            fom=0.0,
            sensor_mode=sensor_mode,
            phase_tm=phase_tm,
            phase_te=phase_te,
            phase_diff=phase_diff,
            reflectance_noisy=R_vals_noisy,
            transmittance_noisy=T_vals_noisy,
            phase_diff_noisy=phase_diff_noisy
        )
    else:
        angles = np.linspace(30, 85, 400)
        try:
            R_tm_arr, T_tm_arr, r_tm_arr = calculate_tmm(req.wavelength_nm, angles, layers, 'TM', return_coefficient=True, temperature_c=req.temperature_c)
            R_te_arr, T_te_arr, r_te_arr = calculate_tmm(req.wavelength_nm, angles, layers, 'TE', return_coefficient=True, temperature_c=req.temperature_c)
            
            R_vals = (R_tm_arr if req.polarization == 'TM' else R_te_arr).tolist()
            T_vals = (T_tm_arr if req.polarization == 'TM' else T_te_arr).tolist()
            
            phase_tm_arr = np.angle(r_tm_arr)
            phase_te_arr = np.angle(r_te_arr)
            diff_arr = phase_tm_arr - phase_te_arr
            diff_wrapped = np.arctan2(np.sin(diff_arr), np.cos(diff_arr))
            
            phase_tm = phase_tm_arr.tolist()
            phase_te = phase_te_arr.tolist()
            phase_diff = diff_wrapped.tolist()
        except Exception as e:
            print(f"ERROR in angular TMM calculation: {e}")
            raise e
        
        min_idx = np.argmin(R_vals)
        res_angle = float(angles[min_idx])
        min_R = float(R_vals[min_idx])
        
        from backend.core.engine import calculate_fwhm
        fwhm = calculate_fwhm(angles, R_vals, res_angle)
        
        R_vals_noisy = None
        T_vals_noisy = None
        phase_diff_noisy = None
        if req.snr_db is not None:
            R_vals_noisy = add_gaussian_noise(R_vals, req.snr_db, is_phase=False)
            T_vals_noisy = add_gaussian_noise(T_vals, req.snr_db, is_phase=False)
            phase_diff_noisy = add_gaussian_noise(phase_diff, req.snr_db, is_phase=True)
        
        return ReflectanceResponse(
            angles=angles.tolist(),
            reflectance=R_vals,
            transmittance=T_vals,
            resonance_angle=res_angle,
            min_reflectance=min_R,
            fwhm=float(fwhm),
            fom=0.0,
            sensor_mode=sensor_mode,
            phase_tm=phase_tm,
            phase_te=phase_te,
            phase_diff=phase_diff,
            reflectance_noisy=R_vals_noisy,
            transmittance_noisy=T_vals_noisy,
            phase_diff_noisy=phase_diff_noisy
        )


@app.post("/api/simulate/field", response_model=FieldProfileResponse)
def simulate_field(req: SimulationWithAngleRequest):
    layers = [layer.model_dump() for layer in req.layers]
    
    z, E_sq, E_complex = calculate_field_profile(
        req.wavelength_nm, req.theta_deg, layers, req.polarization, return_complex=True, temperature_c=req.temperature_c
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
    
    # Analytical penetration depth L, propagation length Le and field enhancement calculation
    penetration_depth = None
    propagation_length = None
    enhancement_factor = None
    
    try:
        n_prisma = get_refractive_index(layers[0], req.wavelength_nm)
        n_analito = get_refractive_index(layers[-1], req.wavelength_nm)
        
        theta_rad = np.radians(req.theta_deg)
        eps_analito = n_analito ** 2
        
        # 1. Penetration depth
        term = eps_analito - (n_prisma * np.sin(theta_rad)) ** 2
        sqrt_term = np.lib.scimath.sqrt(term)
        im_part = np.abs(np.imag(sqrt_term))
        
        if im_part > 1e-9:
            penetration_depth = float(req.wavelength_nm / (2 * np.pi * im_part))
            
        # 2. Field Enhancement Factor (max of |E|^2)
        enhancement_factor = float(np.max(E_sq))
        
        # 3. Propagation length along the interface (Le)
        metal_layer = None
        for L in layers[1:-1]:
            n_c = get_refractive_index(L, req.wavelength_nm)
            eps_c = n_c ** 2
            if eps_c.real < 0:
                metal_layer = L
                break
                
        if metal_layer is not None:
            n_m = get_refractive_index(metal_layer, req.wavelength_nm)
            eps_m = n_m ** 2
            eps_d = eps_analito
            
            spp_term = (eps_m * eps_d) / (eps_m + eps_d)
            spp_sqrt = np.lib.scimath.sqrt(spp_term)
            im_kx = np.imag(spp_sqrt)
            
            if np.abs(im_kx) > 1e-9:
                propagation_length = float(req.wavelength_nm / (4 * np.pi * np.abs(im_kx)))
                
    except Exception as e:
        print(f"Error calculating field profile parameters: {e}")
        
    # 2D Field Map Calculation
    field_2d = None
    x_2d_list = None
    try:
        k0 = 2 * np.pi / req.wavelength_nm
        n0 = get_refractive_index(layers[0], req.wavelength_nm)
        sin0 = np.sin(np.radians(req.theta_deg))
        kx = k0 * n0 * sin0
        
        x_2d = np.linspace(0, 1000, 100)
        # Vectorized outer-product for fast 2D field computation
        phase_factor = np.exp(1j * kx * x_2d)
        field_matrix_2d = np.real(E_complex[:, np.newaxis] * phase_factor[np.newaxis, :])
        
        field_2d = field_matrix_2d.tolist()
        x_2d_list = x_2d.tolist()
    except Exception as e:
        print(f"Error calculating 2D field map: {e}")

    return FieldProfileResponse(
        z=z.tolist(),
        E_sq=E_sq.tolist(),
        layer_bounds=bounds,
        materials=materials,
        penetration_depth=penetration_depth,
        propagation_length=propagation_length,
        enhancement_factor=enhancement_factor,
        field_2d=field_2d,
        x_2d=x_2d_list
    )

@app.post("/api/optimize", response_model=OptimizationResponse)
def optimize_structure(req: OptimizationRequest):
    target = req.target if req.target is not None else "Minimizar Reflectancia"
    wl = req.wavelength_nm
    pol = req.polarization

    def objective(d_values):
        temp_layers = [L.model_dump() for L in req.layers]
        for i, idx in enumerate(req.optimize_indices):
            if temp_layers[idx]['material'] == "Grafeno":
                num_layers = int(np.round(d_values[i]))
                temp_layers[idx]['custom_layers'] = num_layers
                temp_layers[idx]['d'] = float(num_layers * 0.335)
            else:
                temp_layers[idx]['d'] = float(d_values[i])
        
        # Fast coarse angular scan (80 points) to locate dip and FWHM
        angles_opt = np.linspace(35, 80, 80)
        rs, _ = calculate_tmm(wl, angles_opt, temp_layers, pol)
        
        min_R = np.min(rs)
        min_idx = np.argmin(rs)
        
        # Parabolic interpolation for sub-grid dip angle precision
        if min_idx == 0 or min_idx == len(rs) - 1:
            res_angle = float(angles_opt[min_idx])
        else:
            x1, x2, x3 = angles_opt[min_idx-1], angles_opt[min_idx], angles_opt[min_idx+1]
            y1, y2, y3 = rs[min_idx-1], rs[min_idx], rs[min_idx+1]
            denom = y3 - 2 * y2 + y1
            if abs(denom) < 1e-9:
                res_angle = float(x2)
            else:
                h = x2 - x1
                res_angle = float(x2 - (h / 2.0) * (y3 - y1) / denom)
        
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
            
            rs_pert, _ = calculate_tmm(wl, angles_opt, temp_layers_perturbed, pol)
            min_idx_pert = np.argmin(rs_pert)
            
            # Parabolic interpolation for perturbed dip
            if min_idx_pert == 0 or min_idx_pert == len(rs_pert) - 1:
                res_angle_pert = float(angles_opt[min_idx_pert])
            else:
                x1, x2, x3 = angles_opt[min_idx_pert-1], angles_opt[min_idx_pert], angles_opt[min_idx_pert+1]
                y1, y2, y3 = rs_pert[min_idx_pert-1], rs_pert[min_idx_pert], rs_pert[min_idx_pert+1]
                denom = y3 - 2 * y2 + y1
                if abs(denom) < 1e-9:
                    res_angle_pert = float(x2)
                else:
                    h = x2 - x1
                    res_angle_pert = float(x2 - (h / 2.0) * (y3 - y1) / denom)
            
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
        
    result = differential_evolution(objective, bounds, seed=42, maxiter=15, popsize=8)
    
    optimized_layers = [L.model_copy() for L in req.layers]
    for i, idx in enumerate(req.optimize_indices):
        if optimized_layers[idx].material == "Grafeno":
            num_layers = int(np.round(result.x[i]))
            optimized_layers[idx].custom_layers = num_layers
            optimized_layers[idx].d = float(num_layers * 0.335)
        else:
            optimized_layers[idx].d = float(result.x[i])
        
    # Calculate actual min reflectance of optimized configuration
    optimized_layers_dump = [L.model_dump() for L in optimized_layers]
    angles = np.linspace(35, 80, 300)
    actual_min_R_arr, _ = calculate_tmm(req.wavelength_nm, angles, optimized_layers_dump, req.polarization)
    actual_min_R = float(np.min(actual_min_R_arr))
        
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
        angles_arr = np.array(angles)
        for wl in wavelengths:
            R_arr, _ = calculate_tmm(wl, angles_arr, layers, req.polarization)
            matrix.append(R_arr.tolist())
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
    
    # Precalculate Langmuir parameters
    ka = req.ka
    kd = req.kd
    c = req.concentration
    t_assoc = req.t_assoc
    
    eq_ratio = (ka * c) / (ka * c + kd) if (ka * c + kd) > 0 else 0.0
    rate = ka * c + kd
    theta_assoc = eq_ratio * (1.0 - np.exp(-rate * t_assoc))
    
    # 0. Solve for coverage ratio (ratio_vals)
    ratio_vals = []
    if req.use_mass_transport:
        # F: Flow rate in uL/min, D: Diffusion coef in 10^-10 m^2/s
        F = req.flow_rate if req.flow_rate is not None else 50.0
        D = req.diffusion_coef if req.diffusion_coef is not None else 1.0
        
        # Calculate mass transport coefficient km (s^-1)
        # Empirical scaling: at D=1, F=50, km = 15.0 s^-1
        km = 15.0 * (D ** (2.0 / 3.0)) * ((F / 50.0) ** (1.0 / 3.0))
        
        # Equivalent maximum surface concentration capacity (M)
        beta = 1e-5
        
        # Sub-stepped Euler integration for numerical stability
        steps = 6000
        dt = req.t_total / steps
        theta = 0.0
        c_s = 0.0
        t = 0.0
        current_step = 0
        
        for t_target in t_vals:
            while t < t_target and current_step < steps:
                c_bulk = c if t <= t_assoc else 0.0
                
                # Derivatives
                dtheta_dt = ka * c_s * (1.0 - theta) - kd * theta
                dcs_dt = km * (c_bulk - c_s) - beta * dtheta_dt
                
                # Integration
                theta += dtheta_dt * dt
                c_s += dcs_dt * dt
                
                # Physical bounds
                theta = max(0.0, min(1.0, theta))
                c_s = max(0.0, c_s)
                
                t += dt
                current_step += 1
            ratio_vals.append(theta)
    else:
        for t in t_vals:
            if t <= t_assoc:
                ratio = eq_ratio * (1.0 - np.exp(-rate * t))
            else:
                ratio = theta_assoc * np.exp(-kd * (t - t_assoc))
            ratio_vals.append(ratio)
            
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
            r_vals, _ = calculate_tmm(req.wavelength_nm, angles, layers_config, req.polarization)
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
            r_vals, _ = calculate_tmm(req.wavelength_nm, angles, layers_config, req.polarization)
            return float(angles[np.argmin(r_vals)])

    # 1. Calculate baseline resonance (at t=0, adlayer thickness = 0)
    try:
        baseline = find_resonance_full(original_layers)
    except Exception as e:
        print(f"Error calculating baseline resonance: {e}")
        raise HTTPException(status_code=500, detail=f"Error al calcular la resonancia base: {str(e)}")
        
    points = []
    
    # 2. Run simulation over time
    for idx, t in enumerate(t_vals):
        ratio = ratio_vals[idx]
        
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
            r_vals, _ = calculate_tmm(req.wavelength_nm, angles, layers_config, req.polarization)
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


@app.post("/api/fit", response_model=CurveFitResponse)
def fit_curve(req: CurveFitRequest):
    x_exp = np.array(req.x_exp)
    y_exp = np.array(req.y_exp)
    
    if len(x_exp) != len(y_exp) or len(x_exp) == 0:
        raise HTTPException(
            status_code=400, 
            detail="Los datos experimentales X e Y deben tener el mismo tamaño y no estar vacíos."
        )
    
    x0 = [p.guess for p in req.parameters]
    bounds = [(p.min_val, p.max_val) for p in req.parameters]
    
    def loss_func(params_to_test):
        if req.interrogation_mode == "angular":
            wl = req.wavelength_nm
            local_layers = [L.model_dump() for L in req.layers]
            for idx, p in enumerate(req.parameters):
                val = float(params_to_test[idx])
                layer_idx = p.layer_index
                param_type = p.parameter
                
                if param_type == "d":
                    local_layers[layer_idx]["d"] = val
                else:
                    orig_complex = get_refractive_index(req.layers[layer_idx].model_dump(), wl)
                    local_layers[layer_idx]["material"] = "Personalizado (Manual)"
                    if param_type == "n":
                        local_layers[layer_idx]["custom_n"] = val
                        local_layers[layer_idx]["custom_k"] = float(orig_complex.imag)
                    elif param_type == "k":
                        local_layers[layer_idx]["custom_n"] = float(orig_complex.real)
                        local_layers[layer_idx]["custom_k"] = val
            try:
                R_arr, _ = calculate_tmm(wl, req.x_exp, local_layers, req.polarization)
                y_sim = R_arr
            except Exception:
                y_sim = np.ones_like(req.x_exp)
        else:
            y_sim = []
            for i, x in enumerate(req.x_exp):
                wl = x
                theta = req.fixed_angle_deg
                local_layers = [L.model_dump() for L in req.layers]
                for idx, p in enumerate(req.parameters):
                    val = float(params_to_test[idx])
                    layer_idx = p.layer_index
                    param_type = p.parameter
                    
                    if param_type == "d":
                        local_layers[layer_idx]["d"] = val
                    else:
                        orig_complex = get_refractive_index(req.layers[layer_idx].model_dump(), wl)
                        local_layers[layer_idx]["material"] = "Personalizado (Manual)"
                        if param_type == "n":
                            local_layers[layer_idx]["custom_n"] = val
                            local_layers[layer_idx]["custom_k"] = float(orig_complex.imag)
                        elif param_type == "k":
                            local_layers[layer_idx]["custom_n"] = float(orig_complex.real)
                            local_layers[layer_idx]["custom_k"] = val
                try:
                    R, _ = calculate_tmm(wl, theta, local_layers, req.polarization)
                    y_sim.append(float(R))
                except Exception:
                    y_sim.append(1.0)
            y_sim = np.array(y_sim)
                
        return float(np.mean((y_sim - y_exp) ** 2))

    # Pre-calculate initial curve
    if req.interrogation_mode == "angular":
        wl = req.wavelength_nm
        local_layers = [L.model_dump() for L in req.layers]
        for p in req.parameters:
            layer_idx = p.layer_index
            val = p.guess
            if p.parameter == "d":
                local_layers[layer_idx]["d"] = val
            else:
                orig_complex = get_refractive_index(req.layers[layer_idx].model_dump(), wl)
                local_layers[layer_idx]["material"] = "Personalizado (Manual)"
                if p.parameter == "n":
                    local_layers[layer_idx]["custom_n"] = val
                    local_layers[layer_idx]["custom_k"] = float(orig_complex.imag)
                elif p.parameter == "k":
                    local_layers[layer_idx]["custom_n"] = float(orig_complex.real)
                    local_layers[layer_idx]["custom_k"] = val
        try:
            R_arr, _ = calculate_tmm(wl, req.x_exp, local_layers, req.polarization)
            y_initial = R_arr.tolist()
        except Exception:
            y_initial = [1.0] * len(req.x_exp)
    else:
        y_initial = []
        for x in req.x_exp:
            wl = x
            theta = req.fixed_angle_deg
            local_layers = [L.model_dump() for L in req.layers]
            for p in req.parameters:
                layer_idx = p.layer_index
                val = p.guess
                if p.parameter == "d":
                    local_layers[layer_idx]["d"] = val
                else:
                    orig_complex = get_refractive_index(req.layers[layer_idx].model_dump(), wl)
                    local_layers[layer_idx]["material"] = "Personalizado (Manual)"
                    if p.parameter == "n":
                        local_layers[layer_idx]["custom_n"] = val
                        local_layers[layer_idx]["custom_k"] = float(orig_complex.imag)
                    elif p.parameter == "k":
                        local_layers[layer_idx]["custom_n"] = float(orig_complex.real)
                        local_layers[layer_idx]["custom_k"] = val
            try:
                R, _ = calculate_tmm(wl, theta, local_layers, req.polarization)
                y_initial.append(float(R))
            except Exception:
                y_initial.append(1.0)

    try:
        res = minimize(loss_func, x0, bounds=bounds, method='L-BFGS-B')
        optimized_vals = res.x
        rmse = float(np.sqrt(res.fun))
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error en la optimización del ajuste de curvas: {str(e)}"
        )
    
    # Calculate optimized final curve
    if req.interrogation_mode == "angular":
        wl = req.wavelength_nm
        local_layers = [L.model_dump() for L in req.layers]
        for idx, p in enumerate(req.parameters):
            layer_idx = p.layer_index
            val = float(optimized_vals[idx])
            if p.parameter == "d":
                local_layers[layer_idx]["d"] = val
            else:
                orig_complex = get_refractive_index(req.layers[layer_idx].model_dump(), wl)
                local_layers[layer_idx]["material"] = "Personalizado (Manual)"
                if p.parameter == "n":
                    local_layers[layer_idx]["custom_n"] = val
                    local_layers[layer_idx]["custom_k"] = float(orig_complex.imag)
                elif p.parameter == "k":
                    local_layers[layer_idx]["custom_n"] = float(orig_complex.real)
                    local_layers[layer_idx]["custom_k"] = val
        try:
            R_arr, _ = calculate_tmm(wl, req.x_exp, local_layers, req.polarization)
            y_sim = R_arr.tolist()
        except Exception:
            y_sim = [1.0] * len(req.x_exp)
    else:
        y_sim = []
        for x in req.x_exp:
            wl = x
            theta = req.fixed_angle_deg
            local_layers = [L.model_dump() for L in req.layers]
            for idx, p in enumerate(req.parameters):
                layer_idx = p.layer_index
                val = float(optimized_vals[idx])
                if p.parameter == "d":
                    local_layers[layer_idx]["d"] = val
                else:
                    orig_complex = get_refractive_index(req.layers[layer_idx].model_dump(), wl)
                    local_layers[layer_idx]["material"] = "Personalizado (Manual)"
                    if p.parameter == "n":
                        local_layers[layer_idx]["custom_n"] = val
                        local_layers[layer_idx]["custom_k"] = float(orig_complex.imag)
                    elif p.parameter == "k":
                        local_layers[layer_idx]["custom_n"] = float(orig_complex.real)
                        local_layers[layer_idx]["custom_k"] = val
            try:
                R, _ = calculate_tmm(wl, theta, local_layers, req.polarization)
                y_sim.append(float(R))
            except Exception:
                y_sim.append(1.0)
            
    optimized_params = []
    for idx, p in enumerate(req.parameters):
        opt_p = p.model_copy()
        opt_p.optimized_value = float(optimized_vals[idx])
        optimized_params.append(opt_p)
        
    return CurveFitResponse(
        optimized_parameters=optimized_params,
        rmse=rmse,
        y_sim=y_sim,
        y_initial=y_initial
    )


@app.post("/api/simulate/thermal-sweep", response_model=ThermalSweepResponse)
def simulate_thermal_sweep(req: SimulationRequest):
    layers = [layer.model_dump() for layer in req.layers]
    temperatures = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    curves = []
    
    if req.interrogation_mode == "spectral":
        wls = np.linspace(400, 1000, 300)
        fixed_angle = req.fixed_angle_deg if req.fixed_angle_deg is not None else 45.0
        
        for temp in temperatures:
            R_vals = []
            T_vals = []
            for wl in wls:
                # We use TM or TE based on request polarization
                pol = req.polarization
                R_tm, T_tm = calculate_tmm(wl, fixed_angle, layers, pol, temperature_c=temp)
                R_vals.append(float(R_tm))
                T_vals.append(float(T_tm))
            min_idx = np.argmin(R_vals)
            res_wl = float(wls[min_idx])
            curves.append(ThermalSweepCurve(
                temperature_c=temp,
                reflectance=R_vals,
                transmittance=T_vals,
                resonance_wavelength=res_wl
            ))
            
        return ThermalSweepResponse(
            wavelengths=wls.tolist(),
            curves=curves
        )
    else:
        angles = np.linspace(30, 85, 400)
        for temp in temperatures:
            pol = req.polarization
            R_vals_arr, T_vals_arr = calculate_tmm(req.wavelength_nm, angles, layers, pol, temperature_c=temp)
            R_vals = R_vals_arr.tolist()
            T_vals = T_vals_arr.tolist()
            min_idx = np.argmin(R_vals)
            res_angle = float(angles[min_idx])
            curves.append(ThermalSweepCurve(
                temperature_c=temp,
                reflectance=R_vals,
                transmittance=T_vals,
                resonance_angle=res_angle
            ))
            
        return ThermalSweepResponse(
            angles=angles.tolist(),
            curves=curves
        )


@app.post("/api/simulate/calibration", response_model=CalibrationResponse)
def simulate_calibration(req: CalibrationRequest):
    layers = [layer.model_dump() for layer in req.layers]
    
    n_vals = np.linspace(req.n_start, req.n_end, req.steps)
    resonance_values = []
    
    if req.interrogation_mode == "spectral":
        x_grid = np.linspace(400, 1000, 600)
    else:
        x_grid = np.linspace(30, 85, 600)
        
    for n_analyte in n_vals:
        layers[-1]["custom_n"] = float(n_analyte)
        layers[-1]["material"] = "Personalizado (Manual)"
        layers[-1]["custom_k"] = 0.0
        
        if req.interrogation_mode == "spectral":
            R_vals = []
            for x in x_grid:
                R, _ = calculate_tmm(x, req.fixed_angle_deg or 45.0, layers, req.polarization, temperature_c=req.temperature_c)
                R_vals.append(float(R))
        else:
            R_vals_arr, _ = calculate_tmm(req.wavelength_nm, x_grid, layers, req.polarization, temperature_c=req.temperature_c)
            R_vals = R_vals_arr.tolist()
            
        min_idx = np.argmin(R_vals)
        if min_idx == 0 or min_idx == len(R_vals) - 1:
            res_val = float(x_grid[min_idx])
        else:
            x1, x2, x3 = x_grid[min_idx-1], x_grid[min_idx], x_grid[min_idx+1]
            y1, y2, y3 = R_vals[min_idx-1], R_vals[min_idx], R_vals[min_idx+1]
            denom = y3 - 2 * y2 + y1
            if abs(denom) < 1e-9:
                res_val = float(x2)
            else:
                h = x2 - x1
                res_val = float(x2 - (h / 2.0) * (y3 - y1) / denom)
                
        resonance_values.append(res_val)
        
    base_resonance = resonance_values[0]
    shifts = [val - base_resonance for val in resonance_values]
    
    X = np.array(n_vals)
    Y = np.array(resonance_values)
    slope, intercept = np.polyfit(X, Y, 1)
    
    y_pred = slope * X + intercept
    ss_res = np.sum((Y - y_pred) ** 2)
    ss_tot = np.sum((Y - np.mean(Y)) ** 2)
    r_squared = float(1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0)
    
    fit_line = y_pred.tolist()
    
    points = []
    for i in range(len(n_vals)):
        points.append({
            "n": float(n_vals[i]),
            "resonance_value": float(resonance_values[i]),
            "shift": float(shifts[i])
        })
        
    return CalibrationResponse(
        points=points,
        slope=float(slope),
        intercept=float(intercept),
        r_squared=r_squared,
        fit_line=fit_line,
        interrogation_mode=req.interrogation_mode
    )


@app.post("/api/simulate/montecarlo", response_model=MonteCarloResponse)
def simulate_montecarlo(req: MonteCarloRequest):
    nominal_layers = [L.model_dump() for L in req.layers]
    
    if req.interrogation_mode == "spectral":
        x_grid = np.linspace(400, 1000, 200)
    else:
        x_grid = np.linspace(30, 85, 300)
        
    # 1. Calculate nominal curve
    if req.interrogation_mode == "spectral":
        nominal_curve = []
        for wl in x_grid:
            R, _ = calculate_tmm(wl, req.fixed_angle_deg or 45.0, nominal_layers, req.polarization, temperature_c=req.temperature_c)
            nominal_curve.append(float(R))
    else:
        R_nom_arr, _ = calculate_tmm(req.wavelength_nm, x_grid, nominal_layers, req.polarization, temperature_c=req.temperature_c)
        nominal_curve = R_nom_arr.tolist()
        
    # 2. Monte Carlo simulation loop
    trial_curves = []
    resonance_values = []
    success_count = 0
    
    is_spectral = (req.interrogation_mode == "spectral")
    max_acceptable_fwhm = 150.0 if is_spectral else 15.0
    max_acceptable_min_r = 0.35
    
    from backend.core.engine import calculate_fwhm
    
    for _ in range(req.runs):
        trial_layers = [L.copy() for L in nominal_layers]
        
        # Apply perturbations
        for pert in req.perturbations:
            idx = pert.layer_index
            if idx < 0 or idx >= len(trial_layers):
                continue
            if pert.std_d and pert.std_d > 0.0:
                trial_layers[idx]["d"] = max(0.0, float(np.random.normal(nominal_layers[idx]["d"], pert.std_d)))
            if pert.std_n and pert.std_n > 0.0:
                trial_layers[idx]["delta_n"] = float(np.random.normal(0.0, pert.std_n))
            if pert.std_k and pert.std_k > 0.0:
                trial_layers[idx]["delta_k"] = float(np.random.normal(0.0, pert.std_k))
                
        # Simulate
        if is_spectral:
            R_trial = []
            for wl in x_grid:
                R, _ = calculate_tmm(wl, req.fixed_angle_deg or 45.0, trial_layers, req.polarization, temperature_c=req.temperature_c)
                R_trial.append(float(R))
        else:
            R_trial_arr, _ = calculate_tmm(req.wavelength_nm, x_grid, trial_layers, req.polarization, temperature_c=req.temperature_c)
            R_trial = R_trial_arr.tolist()
            
        # Analyze resonance
        min_idx = np.argmin(R_trial)
        min_r = R_trial[min_idx]
        
        # Sub-grid dip interpolation
        if min_idx == 0 or min_idx == len(R_trial) - 1:
            res_val = float(x_grid[min_idx])
        else:
            x1, x2, x3 = x_grid[min_idx-1], x_grid[min_idx], x_grid[min_idx+1]
            y1, y2, y3 = R_trial[min_idx-1], R_trial[min_idx], R_trial[min_idx+1]
            denom = y3 - 2 * y2 + y1
            if abs(denom) < 1e-9:
                res_val = float(x2)
            else:
                h = x2 - x1
                res_val = float(x2 - (h / 2.0) * (y3 - y1) / denom)
                
        # FWHM
        fwhm = calculate_fwhm(x_grid, R_trial, res_val)
        
        # Check yield criteria
        is_success = (min_r <= max_acceptable_min_r) and (fwhm > 0) and (fwhm <= max_acceptable_fwhm)
        if is_success:
            success_count += 1
            
        resonance_values.append(res_val)
        trial_curves.append(R_trial)
        
    # Calculate statistics
    resonance_values = np.array(resonance_values)
    mean_val = float(np.mean(resonance_values))
    median_val = float(np.median(resonance_values))
    std_val = float(np.std(resonance_values))
    ci_lower = float(np.percentile(resonance_values, 2.5))
    ci_upper = float(np.percentile(resonance_values, 97.5))
    yield_percent = float((success_count / req.runs) * 100.0)
    
    if yield_percent >= 95.0:
        yield_msg = "Excelente tolerancia física. El sensor es altamente estable frente a variaciones de manufactura."
    elif yield_percent >= 80.0:
        yield_msg = "Tolerancia física moderada. Se observan derivas leves de resonancia pero mantiene calidad aceptable."
    else:
        yield_msg = "Baja tolerancia física. El sensor presenta alta sensibilidad a variaciones de espesor/índice (dip poco definido)."
        
    # Compute percentiles for envelope plot
    trial_curves_arr = np.array(trial_curves)
    p5_curve = np.percentile(trial_curves_arr, 5, axis=0).tolist()
    p95_curve = np.percentile(trial_curves_arr, 95, axis=0).tolist()
    
    # Pick sample curves
    sample_indices = np.linspace(0, len(trial_curves)-1, min(15, len(trial_curves)), dtype=int)
    sample_curves = [trial_curves[idx] for idx in sample_indices]
    
    stats = MonteCarloStats(
        mean=mean_val,
        median=median_val,
        std=std_val,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        yield_percent=yield_percent,
        yield_message=yield_msg
    )
    
    return MonteCarloResponse(
        x_grid=x_grid.tolist(),
        nominal_curve=nominal_curve,
        p5_curve=p5_curve,
        p95_curve=p95_curve,
        sample_curves=sample_curves,
        resonance_values=resonance_values.tolist(),
        stats=stats
    )


@app.post("/api/simulate/phase-sensitivity", response_model=PhaseSensitivityResponse)
def simulate_phase_sensitivity(req: PhaseSensitivityRequest):
    nominal_layers = [L.model_dump() for L in req.layers]
    perturbed_layers = [L.copy() for L in nominal_layers]
    perturbed_layers[-1]["delta_n"] = req.delta_n or 1e-4
    
    if req.interrogation_mode == "spectral":
        x_grid = np.linspace(400, 1000, 400)
    else:
        x_grid = np.linspace(30, 85, 500)
        
    if req.interrogation_mode == "spectral":
        R_nom_tm, R_nom_te = [], []
        phi_nom_tm, phi_nom_te = [], []
        R_pert_tm, R_pert_te = [], []
        phi_pert_tm, phi_pert_te = [], []
        
        for wl in x_grid:
            _, _, r_nom_tm = calculate_tmm(wl, req.fixed_angle_deg or 45.0, nominal_layers, 'TM', return_coefficient=True, temperature_c=req.temperature_c)
            _, _, r_nom_te = calculate_tmm(wl, req.fixed_angle_deg or 45.0, nominal_layers, 'TE', return_coefficient=True, temperature_c=req.temperature_c)
            
            _, _, r_pert_tm = calculate_tmm(wl, req.fixed_angle_deg or 45.0, perturbed_layers, 'TM', return_coefficient=True, temperature_c=req.temperature_c)
            _, _, r_pert_te = calculate_tmm(wl, req.fixed_angle_deg or 45.0, perturbed_layers, 'TE', return_coefficient=True, temperature_c=req.temperature_c)
            
            R_nom_tm.append(np.abs(r_nom_tm)**2)
            R_nom_te.append(np.abs(r_nom_te)**2)
            phi_nom_tm.append(np.angle(r_nom_tm))
            phi_nom_te.append(np.angle(r_nom_te))
            
            R_pert_tm.append(np.abs(r_pert_tm)**2)
            R_pert_te.append(np.abs(r_pert_te)**2)
            phi_pert_tm.append(np.angle(r_pert_tm))
            phi_pert_te.append(np.angle(r_pert_te))
            
        R_nom_tm = np.array(R_nom_tm)
        R_nom_te = np.array(R_nom_te)
        phi_nom_tm = np.array(phi_nom_tm)
        phi_nom_te = np.array(phi_nom_te)
        
        R_pert_tm = np.array(R_pert_tm)
        R_pert_te = np.array(R_pert_te)
        phi_pert_tm = np.array(phi_pert_tm)
        phi_pert_te = np.array(phi_pert_te)
    else:
        R_nom_tm_arr, _, r_nom_tm = calculate_tmm(req.wavelength_nm, x_grid, nominal_layers, 'TM', return_coefficient=True, temperature_c=req.temperature_c)
        R_nom_te_arr, _, r_nom_te = calculate_tmm(req.wavelength_nm, x_grid, nominal_layers, 'TE', return_coefficient=True, temperature_c=req.temperature_c)
        phi_nom_tm = np.angle(r_nom_tm)
        phi_nom_te = np.angle(r_nom_te)
        
        R_pert_tm_arr, _, r_pert_tm = calculate_tmm(req.wavelength_nm, x_grid, perturbed_layers, 'TM', return_coefficient=True, temperature_c=req.temperature_c)
        R_pert_te_arr, _, r_pert_te = calculate_tmm(req.wavelength_nm, x_grid, perturbed_layers, 'TE', return_coefficient=True, temperature_c=req.temperature_c)
        phi_pert_tm = np.angle(r_pert_tm)
        phi_pert_te = np.angle(r_pert_te)
        
        R_nom_tm = R_nom_tm_arr
        R_nom_te = R_nom_te_arr
        R_pert_tm = R_pert_tm_arr
        R_pert_te = R_pert_te_arr

    phase_nom = phi_nom_tm - phi_nom_te
    phase_nom = np.arctan2(np.sin(phase_nom), np.cos(phase_nom))
    
    phase_pert = phi_pert_tm - phi_pert_te
    phase_pert = np.arctan2(np.sin(phase_pert), np.cos(phase_pert))
    
    diff_phase = phase_pert - phase_nom
    diff_phase_wrapped = np.arctan2(np.sin(diff_phase), np.cos(diff_phase))
    
    deriv_phase = diff_phase_wrapped / (req.delta_n or 1e-4)
    
    if req.polarization == 'TM':
        ref_nom = R_nom_tm
        ref_pert = R_pert_tm
    else:
        ref_nom = R_nom_te
        ref_pert = R_pert_te
        
    deriv_intensity = (ref_pert - ref_nom) / (req.delta_n or 1e-4)
    
    abs_deriv_phase = np.abs(deriv_phase)
    max_phase_idx = np.argmax(abs_deriv_phase)
    max_phase_sens = float(deriv_phase[max_phase_idx])
    max_phase_sens_x = float(x_grid[max_phase_idx])
    
    abs_deriv_intensity = np.abs(deriv_intensity)
    max_intensity_idx = np.argmax(abs_deriv_intensity)
    max_intensity_sens = float(deriv_intensity[max_intensity_idx])
    max_intensity_sens_x = float(x_grid[max_intensity_idx])
    
    return PhaseSensitivityResponse(
        x_grid=x_grid.tolist(),
        phase_nominal=phase_nom.tolist(),
        phase_perturbed=phase_pert.tolist(),
        reflectance_nominal=ref_nom.tolist(),
        reflectance_perturbed=ref_pert.tolist(),
        derivative_phase=deriv_phase.tolist(),
        derivative_intensity=deriv_intensity.tolist(),
        max_phase_sensitivity=max_phase_sens,
        max_phase_sensitivity_x=max_phase_sens_x,
        max_intensity_sensitivity=max_intensity_sens,
        max_intensity_sensitivity_x=max_intensity_sens_x,
        interrogation_mode=req.interrogation_mode
    )


@app.post("/api/lrspp/sweep", response_model=LRSPPSweepResponse)
def lrspp_sweep(req: LRSPPSweepRequest):
    wl = req.wavelength_nm
    polarization = req.polarization
    temp_c = req.temperature_c
    
    # 1. Identificar capa metálica si no está especificada
    layers_base = [L.model_dump() for L in req.layers]
    metal_idx = req.metal_layer_index
    if metal_idx is None or metal_idx < 0:
        for i in range(1, len(layers_base) - 1):
            n_c = get_refractive_index(layers_base[i], wl, temp_c)
            eps_c = n_c ** 2
            if eps_c.real < 0:
                metal_idx = i
                break
    
    if metal_idx is None or metal_idx < 0 or metal_idx >= len(layers_base) - 1:
        raise HTTPException(status_code=400, detail="No se encontró una capa metálica en las capas intermedias para el análisis de plasmones.")
    
    # 2. Identificar capa buffer si no está especificada
    buffer_idx = req.buffer_layer_index
    if buffer_idx is None or buffer_idx < 0:
        buffer_idx = metal_idx - 1
        
    if buffer_idx < 0 or buffer_idx >= len(layers_base):
        raise HTTPException(status_code=400, detail="Índice de capa buffer inválido.")

    # 3. Definir rango de barrido
    sweep_values = []
    if req.sweep_type == "metal_thickness":
        sweep_values = np.linspace(5.0, 80.0, 40).tolist()
    elif req.sweep_type == "buffer_index":
        n_analito = get_refractive_index(layers_base[-1], wl, temp_c).real
        sweep_values = np.linspace(n_analito - 0.05, n_analito + 0.05, 40).tolist()
    else:
        raise HTTPException(status_code=400, detail=f"Tipo de barrido '{req.sweep_type}' no soportado.")

    propagation_lengths = []
    penetration_depths = []
    resonance_angles = []
    fwhm_values = []
    is_lrspp = []
    
    for val in sweep_values:
        layers_temp = [L.copy() for L in layers_base]
        
        if req.sweep_type == "metal_thickness":
            layers_temp[metal_idx]['d'] = val
        elif req.sweep_type == "buffer_index":
            layers_temp[buffer_idx]['material'] = 'Personalizado (Manual)'
            layers_temp[buffer_idx]['custom_n'] = val
            layers_temp[buffer_idx]['custom_k'] = 0.0
            
        # Paso 1: Búsqueda gruesa para localizar la zona del dip (300 puntos de 30° a 89.5°)
        angles_coarse = np.linspace(30.0, 89.5, 300)
        R_coarse = calculate_tmm(wl, angles_coarse, layers_temp, polarization, temperature_c=temp_c)[0]
        min_idx_coarse = np.argmin(R_coarse)
        theta_approx = angles_coarse[min_idx_coarse]
        R_min_approx = R_coarse[min_idx_coarse]
        
        # Paso 2: Zoom local alrededor del dip candidato para capturar resonancias ultra-delgadas
        # (1200 puntos en un micro-rango de +-1.0° para resolución angular extrema de ~0.0016°)
        if R_min_approx < 0.99 and 2 < min_idx_coarse < len(angles_coarse) - 3:
            angles_fine = np.linspace(max(30.0, theta_approx - 1.0), min(89.5, theta_approx + 1.0), 1200)
            reflectance = calculate_tmm(wl, angles_fine, layers_temp, polarization, temperature_c=temp_c)[0]
            
            min_idx = np.argmin(reflectance)
            theta_res = angles_fine[min_idx]
            R_min = reflectance[min_idx]
            
            angles_eval = angles_fine
            reflectance_eval = reflectance
        else:
            angles_eval = angles_coarse
            reflectance_eval = R_coarse
            theta_res = theta_approx
            R_min = R_min_approx
            min_idx = min_idx_coarse
            
        # Consideramos dip válido si R_min es menor a 0.98 y no está en los extremos del escaneo
        if R_min < 0.98 and 5 < min_idx < len(angles_eval) - 5:
            from backend.core.engine import calculate_fwhm
            fwhm_deg = calculate_fwhm(angles_eval, reflectance_eval, theta_res)
            
            if fwhm_deg > 0:
                fwhm_rad = np.radians(fwhm_deg)
                n_prisma = get_refractive_index(layers_temp[0], wl, temp_c).real
                cos_theta = np.cos(np.radians(theta_res))
                
                l_prop = wl / (np.pi * n_prisma * cos_theta * fwhm_rad)
                l_prop_um = l_prop / 1000.0
                
                n_a = get_refractive_index(layers_temp[-1], wl, temp_c)
                eps_a = n_a ** 2
                term = eps_a - (n_prisma * np.sin(np.radians(theta_res))) ** 2
                im_part = np.abs(np.imag(np.lib.scimath.sqrt(term)))
                
                if im_part > 1e-9:
                    l_pen = wl / (2 * np.pi * im_part)
                else:
                    l_pen = 0.0
                    
                n_b = get_refractive_index(layers_temp[buffer_idx], wl, temp_c).real
                n_analito = get_refractive_index(layers_temp[-1], wl, temp_c).real
                simetria_optica = abs(n_b - n_analito) < 0.02
                espesor_delgado = layers_temp[metal_idx]['d'] < 25.0
                
                # Califica como LRSPP si hay simetría, metal delgado y la longitud es alta
                is_lrspp_point = simetria_optica and espesor_delgado and (l_prop_um > 25.0)
                
                propagation_lengths.append(float(l_prop_um))
                penetration_depths.append(float(l_pen))
                resonance_angles.append(float(theta_res))
                fwhm_values.append(float(fwhm_deg))
                is_lrspp.append(bool(is_lrspp_point))
                continue
                
        propagation_lengths.append(0.0)
        penetration_depths.append(0.0)
        resonance_angles.append(0.0)
        fwhm_values.append(0.0)
        is_lrspp.append(False)
        
    if req.sweep_type == "metal_thickness":
        max_idx = np.argmax(propagation_lengths)
        max_val = sweep_values[max_idx]
        max_len = propagation_lengths[max_idx]
        
        n_b = get_refractive_index(layers_base[buffer_idx], wl, temp_c).real
        n_analito = get_refractive_index(layers_base[-1], wl, temp_c).real
        simetria = abs(n_b - n_analito) < 0.02
        
        if max_len > 25.0 and simetria:
            msg = f"¡LRSPP detectado con éxito! Longitud de propagación máxima de {max_len:.1f} µm a un espesor metálico de {max_val:.1f} nm. " \
                  f"Esto es posible gracias a la simetría óptica entre el buffer (n={n_b:.3f}) y el analito (n={n_analito:.3f})."
        else:
            msg = f"Longitud de propagación máxima de {max_len:.1f} µm a un espesor de {max_val:.1f} nm. " \
                  f"Para habilitar modos LRSPP de muy bajas pérdidas, asegúrese de que el buffer y el analito tengan índices muy similares " \
                  f"(Diferencia actual: {abs(n_b - n_analito):.3f}) y el metal sea delgado (< 20 nm)."
    else:
        max_idx = np.argmax(propagation_lengths)
        max_val = sweep_values[max_idx]
        max_len = propagation_lengths[max_idx]
        
        n_analito = get_refractive_index(layers_base[-1], wl, temp_c).real
        msg = f"La longitud de propagación máxima es de {max_len:.1f} µm cuando el índice del buffer es {max_val:.3f}. " \
              f"Observe cómo la longitud de propagación cae bruscamente al alejarse del índice del analito (n={n_analito:.3f}), " \
              f"confirmando que el plasmón de rango largo requiere simetría óptica para existir."
              
    return LRSPPSweepResponse(
        sweep_values=sweep_values,
        propagation_lengths=propagation_lengths,
        penetration_depths=penetration_depths,
        resonance_angles=resonance_angles,
        fwhm_values=fwhm_values,
        is_lrspp=is_lrspp,
        message=msg
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
