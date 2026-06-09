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
    snr_db?: number;
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
    reflectance_noisy?: number[];
    transmittance_noisy?: number[];
    phase_diff_noisy?: number[];
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

export interface LayerPerturbation {
    layer_index: number;
    std_d?: number;
    std_n?: number;
    std_k?: number;
}

export interface MonteCarloRequest extends SimulationRequest {
    runs: number;
    perturbations: LayerPerturbation[];
}

export interface MonteCarloStats {
    mean: number;
    median: number;
    std: number;
    ci_lower: number;
    ci_upper: number;
    yield_percent: number;
    yield_message: string;
}

export interface MonteCarloResponse {
    x_grid: number[];
    nominal_curve: number[];
    p5_curve: number[];
    p95_curve: number[];
    sample_curves: number[][];
    resonance_values: number[];
    stats: MonteCarloStats;
}

export interface PhaseSensitivityRequest extends SimulationRequest {
    delta_n?: number;
}

export interface PhaseSensitivityResponse {
    x_grid: number[];
    phase_nominal: number[];
    phase_perturbed: number[];
    reflectance_nominal: number[];
    reflectance_perturbed: number[];
    derivative_phase: number[];
    derivative_intensity: number[];
    max_phase_sensitivity: number;
    max_phase_sensitivity_x: number;
    max_intensity_sensitivity: number;
    max_intensity_sensitivity_x: number;
    interrogation_mode: 'angular' | 'spectral';
}

export interface LRSPPSweepRequest {
    layers: LayerConfig[];
    wavelength_nm: number;
    polarization: 'TM' | 'TE';
    temperature_c?: number;
    sweep_type: 'metal_thickness' | 'buffer_index';
    metal_layer_index?: number;
    buffer_layer_index?: number;
}

export interface LRSPPSweepResponse {
    sweep_values: number[];
    propagation_lengths: number[];
    penetration_depths: number[];
    resonance_angles: number[];
    fwhm_values: number[];
    is_lrspp: boolean[];
    message: string;
}
