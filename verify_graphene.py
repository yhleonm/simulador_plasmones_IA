import numpy as np
import scipy.constants as const
import sys

# Mocking necessary parts of app.py

def calculate_graphene_sigma(wavelength_nm, chemical_potential_eV=0.3, temp_K=300, gamma_eV=0.0001):
    e = const.e             
    hbar = const.hbar       
    kb = const.k            
    c = const.c             
    
    omega = 2 * np.pi * c / (wavelength_nm * 1e-9) 
    mu = chemical_potential_eV * e                  
    kT = kb * temp_K                                
    gamma = gamma_eV * e                            
    
    term1_intra = (1j * e**2 * kT) / (np.pi * hbar**2 * (omega + 1j * 2 * gamma/hbar))
    term2_intra = (mu / kT) + 2 * np.log(np.exp(-mu / kT) + 1)
    sigma_intra = term1_intra * term2_intra
    
    cte_univ = e**2 / (4 * hbar)
    x = (hbar * omega - 2 * mu) / (2 * kT)
    
    real_inter = cte_univ * (0.5 + (1/np.pi) * np.arctan(x))
    
    arg_log = np.abs((hbar * omega - 2 * mu) / (hbar * omega + 2 * mu))
    imag_inter = - (cte_univ / np.pi) * np.log(arg_log)
    
    sigma_inter = real_inter + 1j * imag_inter
    
    return sigma_intra + sigma_inter

def get_refractive_index_mock(layer_info, wavelength_nm):
    material = layer_info['material']
    if material == "Grafeno":
        d_mono = 0.335
        num_layers = layer_info.get('custom_layers', 1)
        # Check if d is being respected or overwritten
        d_from_info = layer_info.get('d', 0.335)
        
        # In app.py, we calculate d_total from num_layers, BUT we also allow 'd' to be passed.
        # Let's ensure consistency.
        d_total = num_layers * d_mono
        
        # CRITICAL CHECK:
        if abs(d_total - d_from_info) > 0.01:
             print(f"WARNING: Thickness mismatch! d_total={d_total}, d_info={d_from_info}")

        mu = layer_info.get('custom_mu', 0.3)
        sigma = calculate_graphene_sigma(wavelength_nm, chemical_potential_eV=mu)
        
        epsilon_0 = const.epsilon_0
        omega = 2 * np.pi * const.c / (wavelength_nm * 1e-9)
        d_meters = d_total * 1e-9
        
        epsilon_graphene = 1 + (1j * sigma) / (epsilon_0 * omega * d_meters)
        return np.sqrt(epsilon_graphene)
    elif material == "Oro (Au)":
        return 0.18 + 1j * 3.0 
    elif material == "Vidrio (BK7)":
        return 1.51 + 0j
    elif material == "Aire / Vacío":
        return 1.0 + 0j
    return 1.0 + 0j

def calculate_tmm_mock(wavelength_nm, theta_deg, layers):
    k0 = 2 * np.pi / wavelength_nm
    theta_rad = np.radians(theta_deg)
    
    ns = [get_refractive_index_mock(L, wavelength_nm) for L in layers]
    ds = [L['d'] for L in layers]
    
    with open("verification_result.txt", "w") as f:
        f.write(f"--- TMM Verification Run ---\n")
        f.write(f"Wavelength: {wavelength_nm} nm, Angle: {theta_deg} deg\n")
        f.write(f"Layers: {[L['material'] for L in layers]}\n")
        f.write(f"Indices: {ns}\n")
        f.write(f"Thicknesses (nm): {ds}\n")
        
        # Check float precision
        for i, d in enumerate(ds):
            if d > 0 and d < 1.0:
                f.write(f"Layer {i} ({layers[i]['material']}) is THIN: {d} nm. Precision check: {d:.20f}\n")
                if d == 0:
                    f.write("ERROR: THICKNESS IS ZERO!\n")
                else:
                    f.write("OK: Thickness is not zero.\n")

        n0 = ns[0]
        sin0 = np.sin(theta_rad)
        
        M = np.identity(2, dtype=complex)
        
        for i in range(len(ns)):
            if i > 0 and i < len(ns) - 1:
                n = ns[i]
                d = ds[i]
                
                cos_theta = np.lib.scimath.sqrt(1 - ((n0 / n) * sin0)**2)
                q = n / cos_theta # TM
                
                delta = k0 * n * d * cos_theta
                
                f.write(f"calc_matrix layer {i} with d={d}\n") # simple trace
                
                m11 = np.cos(delta)
                m12 = (-1j / q) * np.sin(delta)
                m21 = (-1j * q) * np.sin(delta)
                m22 = np.cos(delta)
                
                M_layer = np.array([[m11, m12], [m21, m22]])
                M = np.dot(M, M_layer)
        
        f.write(f"Final Matrix M11: {M[0,0]}\n")
        f.write("--- VERIFICATION COMPLETE ---\n")

# TEST
layers = [
    {"material": "Vidrio (BK7)", "d": 0},
    {"material": "Oro (Au)", "d": 50},
    {"material": "Grafeno", "d": 0.335, "custom_layers": 1, "custom_mu": 0.3},
    {"material": "Aire / Vacío", "d": 0}
]

calculate_tmm_mock(633, 45, layers)
print("Verification script finished.")
