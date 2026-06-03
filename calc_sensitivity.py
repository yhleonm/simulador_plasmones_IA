import numpy as np
import sys

# Force flushing
sys.stdout.reconfigure(line_buffering=True)

# Physics Engine (Replicated from app.py)
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

def find_resonance(layers):
    angles = np.linspace(40, 50, 500)
    R_vals = [calculate_tmm(633, th, layers) for th in angles]
    return angles[np.argmin(R_vals)]

if __name__ == "__main__":
    with open("sensitivity_results.txt", "w") as f:
        f.write("SCRIPT STARTED\n")
        # BASE STRUCTURE
        base_layers = [
            {"material": "Vidrio (BK7)", "d": 0},
            {"material": "Oro (Au)", "d": 50},       
            {"material": "Grafeno", "d": 0.335},     
            {"material": "Aire / Vacío", "d": 0}
        ]

        # 1. Calculate Baseline Angle
        f.write("Calculating baseline...\n")
        angle_base = find_resonance(base_layers)
        f.write(f"Baseline Angle: {angle_base:.4f}\n")

        # 2. Perturb Gold (+1 nm)
        f.write("Perturbing Gold...\n")
        layers_au = [L.copy() for L in base_layers]
        layers_au[1]['d'] += 1.0
        angle_au = find_resonance(layers_au)
        delta_au = abs(angle_au - angle_base)

        # 3. Perturb Graphene (+1 layer = +0.335 nm)
        f.write("Perturbing Graphene...\n")
        layers_gr = [L.copy() for L in base_layers]
        layers_gr[2]['d'] += 0.335 # One extra layer
        # layers_gr[2]['d'] += 1.0 # Compare per nm
        angle_gr = find_resonance(layers_gr)
        delta_gr = abs(angle_gr - angle_base)

        f.write(f"--- SENSITIVITY ANALYSIS ---\n")
        f.write(f"Baseline Angle: {angle_base:.4f} deg\n")
        f.write(f"Delta Angle (Au +1nm): {delta_au:.4f} deg\n")
        
        sens_au = delta_au / 1.0
        
        # Sensitivity per Layer
        f.write(f"Delta Angle (Graphene +1 layer / 0.335nm): {delta_gr:.4f} deg\n")
        
        # Sensitivity per nm
        sens_gr_nm = delta_gr / 0.335
        f.write(f"Sensitivity (deg/nm) - Gold: {sens_au:.4f}\n")
        f.write(f"Sensitivity (deg/nm) - Graphene: {sens_gr_nm:.4f}\n")
        
        ratio = sens_gr_nm / sens_au if sens_au > 0 else 999
        f.write(f"Result: Graphene is {ratio:.2f}x more sensitive per nm.\n")
