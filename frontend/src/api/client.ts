import axios from 'axios';
import type { SimulationRequest, ReflectanceResponse, FieldProfileResponse, OptimizationRequest, Simulation2DRequest, Simulation2DResponse } from '../types';

let rawBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
if (rawBaseUrl && !rawBaseUrl.endsWith('/api') && !rawBaseUrl.endsWith('/api/')) {
    rawBaseUrl = rawBaseUrl.replace(/\/$/, '') + '/api';
}
const API_BASE_URL = rawBaseUrl;

const api = axios.create({
    baseURL: API_BASE_URL,
});

export const simulateReflectance = async (req: SimulationRequest): Promise<ReflectanceResponse> => {
    const response = await api.post('/simulate/reflectance', req);
    return response.data;
};

export const simulateFieldProfile = async (req: SimulationRequest & { theta_deg: number }): Promise<FieldProfileResponse> => {
    const response = await api.post('/simulate/field', req);
    return response.data;
};

export const optimizeStructure = async (req: OptimizationRequest) => {
    const response = await api.post('/optimize', req);
    return response.data;
};

export interface MaterialInfo {
    name: string;
    type: 'built-in' | 'csv';
    file?: string;
}

export const getMaterials = async (): Promise<MaterialInfo[]> => {
    const response = await api.get('/materials');
    return response.data;
};

export const importMaterial = async (file: File, name: string): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', name);
    const response = await api.post('/materials/import', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const simulateReflectance2D = async (req: Simulation2DRequest): Promise<Simulation2DResponse> => {
    const response = await api.post('/simulate/reflectance-2d', req);
    return response.data;
};


