import matplotlib
matplotlib.use('Agg') # Force headless backend

import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
import sys
import os

# Force stdout flushing
sys.stdout.reconfigure(line_buffering=True)

print("--- Script Starting (Headless Mode) ---")

# --- 1. Physics Engine (Replicated from app.py) ---
def get_refractive_index(layer_info, wavelength_nm):
    material = layer_info['material']
    
    if material == "Grafeno":
        return 3.0 + 1.149j  
    elif material == "Oro (Au)":
        return 0.18 + 3.0j 
    elif material == "Vidrio (BK7)":
        return 1.515 + 0j
    elif material == "Aire / Vacío":
        return 1.0 + 0j
    return 1.0 + 0j

def calculate_tmm(wavelength_nm, theta_deg, layers):
    k0 = 2 * np.pi / wavelength_nm
    theta_rad = np.radians(theta_deg)
    
    ns = [get_refractive_index(L, wavelength_nm) for L in layers]
    ds = [L['d'] for L in layers]
    
    n0 = ns[0]
    sin0 = np.sin(theta_rad)
    
    M = np.identity(2, dtype=complex)
    
    for i in range(len(ns)):
        if i == 0 or i == len(ns) - 1: continue
        
        n = ns[i]
        d = ds[i]
        cos_theta = np.lib.scimath.sqrt(1 - ((n0 / n) * sin0)**2)
        q = n / cos_theta # TM
        delta = k0 * n * d * cos_theta
        
        m11 = np.cos(delta)
        m12 = (-1j / q) * np.sin(delta)
        m21 = (-1j * q) * np.sin(delta)
        m22 = np.cos(delta)
        
        M_layer = np.array([[m11, m12], [m21, m22]])
        M = np.dot(M, M_layer)
        
    nN = ns[-1]
    cos_thN = np.lib.scimath.sqrt(1 - ((n0 / nN) * sin0)**2)
    qN = nN / cos_thN # TM
    q0 = n0 / np.lib.scimath.sqrt(1 - sin0**2) # TM

    num = (M[0,0] + M[0,1]*qN)*q0 - (M[1,0] + M[1,1]*qN)
    den = (M[0,0] + M[0,1]*qN)*q0 + (M[1,0] + M[1,1]*qN)
    r = num / den
    R = np.abs(r)**2
    return R

if __name__ == "__main__":
    try:
        # --- 2. Simulation Setup ---
        base_layers = [
            {"material": "Vidrio (BK7)", "d": 0},
            {"material": "Oro (Au)", "d": 50},       
            {"material": "Grafeno", "d": 0.335},     
            {"material": "Aire / Vacío", "d": 0}
        ]

        wl = 633.0 
        n_samples = 300 

        print(f"Generating {n_samples} samples...")

        X = [] 
        y = [] 
        
        # Angles to scan
        angles = np.linspace(40, 50, 200)

        for i in range(n_samples):
            if i % 50 == 0: print(f"Sample {i}/{n_samples}")
            
            d_au = np.random.uniform(40.0, 50.0) # Narrow range to simulate optimization zone
            n_layers = np.random.randint(1, 10)
            d_graphene = n_layers * 0.335
            
            current_layers = [L.copy() for L in base_layers]
            current_layers[1]['d'] = d_au
            current_layers[2]['d'] = d_graphene
            
            R_vals = [calculate_tmm(wl, th, current_layers) for th in angles]
            min_idx = np.argmin(R_vals)
            spr_angle = angles[min_idx]
            
            X.append([d_au, n_layers])
            y.append(spr_angle)
            
        X = np.array(X)
        y = np.array(y)

        print("Training Random Forest Regressor...")
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)

        importances = model.feature_importances_
        feature_names = ["Grosor Oro (nm)", "Capas Grafeno"]

        print("\\n--- Feature Importances ---")
        for name, imp in zip(feature_names, importances):
            print(f"{name}: {imp:.4f}")

        # Plot
        output_path = os.path.abspath("feature_importance.png")
        plt.figure(figsize=(8, 5))
        plt.bar(feature_names, importances, color=['gold', 'black'])
        plt.title("Importancia de Variables en Ángulo de Resonancia")
        plt.ylabel("Importancia Relativa (0-1)")
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.savefig(output_path)
        print(f"Plot saved to: {output_path}")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
