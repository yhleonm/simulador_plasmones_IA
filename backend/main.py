from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
from typing import List

from backend.models.schemas import SimulationRequest, SimulationWithAngleRequest, ReflectanceResponse, FieldProfileResponse, OptimizationRequest, OptimizationResponse
from backend.core.engine import calculate_tmm, calculate_field_profile
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
