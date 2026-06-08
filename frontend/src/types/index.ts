export interface LayerConfig {
    material: string;
    d: number;
    custom_n?: number;
    custom_k?: number;
    custom_layers?: number;
    custom_mu?: number;
    is_effective_medium?: boolean;
    fraction?: number;
    matrix_material?: string;
    inclusion_material?: string;
    model_type?: 'bruggeman' | 'maxwell-garnett';
    custom_dn_dt?: number;
}

export interface SimulationRequest {
    wavelength_nm: number;
    polarization: 'TM' | 'TE';
    layers: LayerConfig[];
    interrogation_mode?: 'angular' | 'spectral';
    fixed_angle_deg?: number;
    temperature_c?: number;
}

export interface OptimizationRequest extends SimulationRequest {
    optimize_indices: number[];
    bounds_min?: number[];
    bounds_max?: number[];
    target?: string;
}

export interface ReflectanceResponse {
    angles?: number[];
    wavelengths?: number[];
    reflectance: number[];
    transmittance?: number[];
    resonance_angle?: number;
    resonance_wavelength?: number;
    min_reflectance?: number;
    fwhm?: number;
    fom?: number;
    sensor_mode?: string;
    phase_tm?: number[];
    phase_te?: number[];
    phase_diff?: number[];
}


export interface FieldProfileResponse {
    z: number[];
    E_sq: number[];
    layer_bounds: number[];
    materials: string[];
    penetration_depth?: number;
    propagation_length?: number;
    enhancement_factor?: number;
    field_2d?: number[][];
    x_2d?: number[];
}

export interface Simulation2DRequest {
    layers: LayerConfig[];
    polarization: 'TM' | 'TE';
    angle_min?: number;
    angle_max?: number;
    angle_steps?: number;
    wl_min?: number;
    wl_max?: number;
    wl_steps?: number;
}

export interface Simulation2DResponse {
    angles: number[];
    wavelengths: number[];
    matrix: number[][];
}

export interface KineticsPoint {
    time: number;
    shift: number;
    resonance: number;
}

export interface KineticsResponse {
    points: KineticsPoint[];
    unit: string;
}

export interface KineticsRequest {
    layers: LayerConfig[];
    wavelength_nm: number;
    polarization: 'TM' | 'TE';
    interrogation_mode: 'angular' | 'spectral';
    fixed_angle_deg?: number;
    ka: number;
    kd: number;
    concentration: number;
    t_assoc: number;
    t_total: number;
    d_max: number;
    n_adlayer: number;
    flow_rate?: number;
    diffusion_coef?: number;
    use_mass_transport?: boolean;
}

export interface PDPPoint {
    value: number;
    resonance: number;
}

export interface XAIVariableData {
    layer_index: number;
    material: string;
    importance: number;
    sweep: PDPPoint[];
}

export interface XAIResponse {
    variables: XAIVariableData[];
}

export interface FitParameterConfig {
    layer_index: number;
    parameter: 'd' | 'n' | 'k';
    guess: number;
    min_val: number;
    max_val: number;
    optimized_value?: number;
}

export interface CurveFitRequest {
    layers: LayerConfig[];
    wavelength_nm: number;
    polarization: 'TM' | 'TE';
    interrogation_mode: 'angular' | 'spectral';
    fixed_angle_deg?: number;
    x_exp: number[];
    y_exp: number[];
    parameters: FitParameterConfig[];
}

export interface CurveFitResponse {
    optimized_parameters: FitParameterConfig[];
    rmse: number;
    y_sim: number[];
    y_initial: number[];
}

export interface XAIRequest {
    layers: LayerConfig[];
    wavelength_nm: number;
    polarization: 'TM' | 'TE';
    interrogation_mode: 'angular' | 'spectral';
    fixed_angle_deg?: number;
    analyze_indices: number[];
    bounds_min: number[];
    bounds_max: number[];
}

export interface ThermalSweepCurve {
    temperature_c: number;
    reflectance: number[];
    transmittance?: number[];
    resonance_angle?: number;
    resonance_wavelength?: number;
}

export interface ThermalSweepResponse {
    angles?: number[];
    wavelengths?: number[];
    curves: ThermalSweepCurve[];
}

export interface CalibrationRequest extends SimulationRequest {
    n_start: number;
    n_end: number;
    steps: number;
}

export interface CalibrationPoint {
    n: number;
    resonance_value: number;
    shift: number;
}

export interface CalibrationResponse {
    points: CalibrationPoint[];
    slope: number;
    intercept: number;
    r_squared: number;
    fit_line: number[];
    interrogation_mode: 'angular' | 'spectral';
}





