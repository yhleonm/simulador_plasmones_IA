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
}

export interface SimulationRequest {
    wavelength_nm: number;
    polarization: 'TM' | 'TE';
    layers: LayerConfig[];
    interrogation_mode?: 'angular' | 'spectral';
    fixed_angle_deg?: number;
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


