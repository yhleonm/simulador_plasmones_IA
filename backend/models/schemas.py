from pydantic import BaseModel, Field
from typing import List, Optional

class LayerConfig(BaseModel):
    model_config = {"protected_namespaces": ()}
    
    material: str
    d: float = Field(..., ge=0, description="Thickness in nm")
    custom_n: Optional[float] = 1.5
    custom_k: Optional[float] = 0.0
    custom_layers: Optional[int] = 1
    custom_mu: Optional[float] = 0.3
    is_effective_medium: Optional[bool] = False
    fraction: Optional[float] = 0.5
    matrix_material: Optional[str] = "Vidrio (BK7)"
    inclusion_material: Optional[str] = "Aire / Vacio"
    model_type: Optional[str] = "bruggeman"
    custom_dn_dt: Optional[float] = 0.0

class SimulationRequest(BaseModel):
    wavelength_nm: float = Field(..., gt=0)
    polarization: str = Field("TM", pattern="^(TM|TE)$")
    layers: List[LayerConfig]
    interrogation_mode: Optional[str] = "angular"
    fixed_angle_deg: Optional[float] = 45.0
    temperature_c: Optional[float] = 20.0

class SimulationWithAngleRequest(SimulationRequest):
    theta_deg: float = Field(..., ge=0, le=90)

class ReflectanceResponse(BaseModel):
    angles: Optional[List[float]] = None
    wavelengths: Optional[List[float]] = None
    reflectance: List[float]
    transmittance: Optional[List[float]] = None
    resonance_angle: Optional[float] = None
    resonance_wavelength: Optional[float] = None
    min_reflectance: Optional[float]
    fwhm: Optional[float] = 0.0
    fom: Optional[float] = 0.0
    sensor_mode: Optional[str] = None
    phase_tm: Optional[List[float]] = None
    phase_te: Optional[List[float]] = None
    phase_diff: Optional[List[float]] = None



class FieldProfileResponse(BaseModel):
    z: List[float]
    E_sq: List[float]
    layer_bounds: List[float]
    materials: List[str]
    penetration_depth: Optional[float] = None
    propagation_length: Optional[float] = None
    enhancement_factor: Optional[float] = None
    field_2d: Optional[List[List[float]]] = None
    x_2d: Optional[List[float]] = None

class OptimizationRequest(SimulationRequest):
    optimize_indices: List[int] = Field(..., description="Indices of layers to optimize")
    bounds_min: Optional[List[float]] = Field(None, description="Minimum search bounds for each optimized layer")
    bounds_max: Optional[List[float]] = Field(None, description="Maximum search bounds for each optimized layer")
    target: Optional[str] = Field("Minimizar Reflectancia", description="Optimization target: Minimizar Reflectancia, Maximizar Sensibilidad, or Maximizar FoM")

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
    flow_rate: Optional[float] = Field(50.0, description="Flow rate in uL/min")
    diffusion_coef: Optional[float] = Field(1.0, description="Diffusion coefficient in 10^-10 m^2/s")
    use_mass_transport: Optional[bool] = Field(True, description="Enable two-compartment mass transport model")

class KineticsPoint(BaseModel):
    time: float
    shift: float
    resonance: float

class KineticsResponse(BaseModel):
    points: List[KineticsPoint]
    unit: str

class XAIRequest(BaseModel):
    layers: List[LayerConfig]
    wavelength_nm: float = Field(633.0, gt=0)
    polarization: str = Field("TM", pattern="^(TM|TE)$")
    interrogation_mode: str = Field("angular", pattern="^(angular|spectral)$")
    fixed_angle_deg: Optional[float] = 45.0
    analyze_indices: List[int]
    bounds_min: List[float]
    bounds_max: List[float]

class PDPPoint(BaseModel):
    value: float
    resonance: float

class XAIVariableData(BaseModel):
    layer_index: int
    material: str
    importance: float
    sweep: List[PDPPoint]

class XAIResponse(BaseModel):
    variables: List[XAIVariableData]


class FitParameterConfig(BaseModel):
    layer_index: int
    parameter: str = Field(..., pattern="^(d|n|k)$", description="Parameter to fit: d (thickness), n (refractive index real part), or k (refractive index imaginary part)")
    guess: float
    min_val: float
    max_val: float
    optimized_value: Optional[float] = None

class CurveFitRequest(BaseModel):
    layers: List[LayerConfig]
    wavelength_nm: float = Field(633.0, gt=0)
    polarization: str = Field("TM", pattern="^(TM|TE)$")
    interrogation_mode: str = Field("angular", pattern="^(angular|spectral)$")
    fixed_angle_deg: Optional[float] = 45.0
    x_exp: List[float] = Field(..., description="Experimental X data (angles or wavelengths)")
    y_exp: List[float] = Field(..., description="Experimental Y data (reflectance)")
    parameters: List[FitParameterConfig] = Field(..., description="Parameters to fit")

class CurveFitResponse(BaseModel):
    optimized_parameters: List[FitParameterConfig]
    rmse: float
    y_sim: List[float]
    y_initial: List[float]


class ThermalSweepCurve(BaseModel):
    temperature_c: float
    reflectance: List[float]
    transmittance: Optional[List[float]] = None
    resonance_angle: Optional[float] = None
    resonance_wavelength: Optional[float] = None

class ThermalSweepResponse(BaseModel):
    angles: Optional[List[float]] = None
    wavelengths: Optional[List[float]] = None
    curves: List[ThermalSweepCurve]


class CalibrationRequest(SimulationRequest):
    n_start: float = Field(1.330, gt=0, description="Starting refractive index of analyte")
    n_end: float = Field(1.350, gt=0, description="Ending refractive index of analyte")
    steps: int = Field(5, ge=3, le=20, description="Number of calibration steps")

class CalibrationPoint(BaseModel):
    n: float
    resonance_value: float
    shift: float

class CalibrationResponse(BaseModel):
    points: List[CalibrationPoint]
    slope: float
    intercept: float
    r_squared: float
    fit_line: List[float]
    interrogation_mode: str






