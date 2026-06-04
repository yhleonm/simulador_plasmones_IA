export interface LayerConfig {
    material: string;
    d: number;
    custom_n?: number;
    custom_k?: number;
    custom_layers?: number;
    custom_mu?: number;
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

