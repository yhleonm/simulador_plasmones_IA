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

