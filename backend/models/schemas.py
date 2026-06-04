from pydantic import BaseModel, Field
from typing import List, Optional

class LayerConfig(BaseModel):
    material: str
    d: float = Field(..., ge=0, description="Thickness in nm")
    custom_n: Optional[float] = 1.5
    custom_k: Optional[float] = 0.0
    custom_layers: Optional[int] = 1
    custom_mu: Optional[float] = 0.3

class SimulationRequest(BaseModel):
    wavelength_nm: float = Field(..., gt=0)
    polarization: str = Field("TM", pattern="^(TM|TE)$")
    layers: List[LayerConfig]
    interrogation_mode: Optional[str] = "angular"
    fixed_angle_deg: Optional[float] = 45.0

class SimulationWithAngleRequest(SimulationRequest):
    theta_deg: float = Field(..., ge=0, le=90)

class ReflectanceResponse(BaseModel):
    angles: Optional[List[float]] = None
    wavelengths: Optional[List[float]] = None
    reflectance: List[float]
    resonance_angle: Optional[float] = None
    resonance_wavelength: Optional[float] = None
    min_reflectance: Optional[float]
    fwhm: Optional[float] = 0.0
    fom: Optional[float] = 0.0


class FieldProfileResponse(BaseModel):
    z: List[float]
    E_sq: List[float]
    layer_bounds: List[float]
    materials: List[str]

class OptimizationRequest(SimulationRequest):
    optimize_indices: List[int] = Field(..., description="Indices of layers to optimize")
    bounds_min: Optional[List[float]] = Field(None, description="Minimum search bounds for each optimized layer")
    bounds_max: Optional[List[float]] = Field(None, description="Maximum search bounds for each optimized layer")

class OptimizationResponse(BaseModel):
    optimized_layers: List[LayerConfig]
    min_reflectance: float

class Simulation2DRequest(BaseModel):
    layers: List[LayerConfig]
    polarization: str = Field("TM", pattern="^(TM|TE)$")
    angle_min: Optional[float] = Field(30.0, ge=0, le=90)
    angle_max: Optional[float] = Field(85.0, ge=0, le=90)
    angle_steps: Optional[int] = Field(80, ge=10, le=200)
    wl_min: Optional[float] = Field(400.0, gt=0)
    wl_max: Optional[float] = Field(900.0, gt=0)
    wl_steps: Optional[int] = Field(80, ge=10, le=200)

class Simulation2DResponse(BaseModel):
    angles: List[float]
    wavelengths: List[float]
    matrix: List[List[float]]

class KineticsRequest(BaseModel):
    layers: List[LayerConfig]
    wavelength_nm: float = Field(633.0, gt=0)
    polarization: str = Field("TM", pattern="^(TM|TE)$")
    interrogation_mode: str = Field("angular", pattern="^(angular|spectral)$")
    fixed_angle_deg: Optional[float] = 45.0
    
    # Kinetic parameters
    ka: float = Field(1e4, description="Association rate constant (M^-1 s^-1)")
    kd: float = Field(1e-3, description="Dissociation rate constant (s^-1)")
    concentration: float = Field(1e-6, description="Analyte concentration (M)")
    t_assoc: float = Field(120, description="Association time (s)")
    t_total: float = Field(300, description="Total simulation time (s)")
    d_max: float = Field(5.0, description="Maximum adlayer thickness (nm)")
    n_adlayer: float = Field(1.45, description="Refractive index of bound adlayer")

class KineticsPoint(BaseModel):
    time: float
    shift: float
    resonance: float

class KineticsResponse(BaseModel):
    points: List[KineticsPoint]
    unit: str


