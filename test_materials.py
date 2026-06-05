import os
import sys
import numpy as np
from backend.core.engine import get_refractive_index, calculate_tmm

wl = 633.0

print("Testing get_refractive_index")

# BK7
bk7_info = {"material": "Vidrio (BK7)", "d": 0.0}
print(f"BK7: {get_refractive_index(bk7_info, wl)}")

# Gold
gold_info = {"material": "Oro (Au)", "d": 45.0}
print(f"Gold: {get_refractive_index(gold_info, wl)}")

# Air
air_info = {"material": "Aire / Vacío", "d": 0.0}
print(f"Air: {get_refractive_index(air_info, wl)}")

# Custom Gold approx at 633nm
custom_gold_info = {"material": "Personalizado (Manual)", "d": 45.0, "custom_n": 0.12, "custom_k": 3.0}
print(f"Custom Gold (n=0.12, k=3.0): {get_refractive_index(custom_gold_info, wl)}")

print("\n--- Testing TMM Reflectance ---")
layers_auto = [
    {"material": "Vidrio (BK7)", "d": 0.0},
    {"material": "Oro (Au)", "d": 45.0},
    {"material": "Aire / Vacío", "d": 0.0}
]

layers_custom = [
    {"material": "Personalizado (Manual)", "d": 0.0, "custom_n": np.real(get_refractive_index(bk7_info, wl)), "custom_k": np.imag(get_refractive_index(bk7_info, wl))},
    {"material": "Personalizado (Manual)", "d": 45.0, "custom_n": np.real(get_refractive_index(gold_info, wl)), "custom_k": np.imag(get_refractive_index(gold_info, wl))},
    {"material": "Personalizado (Manual)", "d": 0.0, "custom_n": 1.0, "custom_k": 0.0}
]

layers_custom_user = [
    {"material": "Personalizado (Manual)", "d": 0.0, "custom_n": 1.515, "custom_k": 0.0},
    {"material": "Personalizado (Manual)", "d": 45.0, "custom_n": 0.12, "custom_k": 3.0}, # typ values for gold
    {"material": "Personalizado (Manual)", "d": 0.0, "custom_n": 1.0, "custom_k": 0.0}
]


print("\n1. Auto Layers (BK7, Gold, Air)")
angles = np.linspace(30, 85, 200)
R_auto = [calculate_tmm(wl, th, layers_auto, 'TM')[0] for th in angles]
print(f"Min R: {np.min(R_auto):.6f} at Angle: {angles[np.argmin(R_auto)]:.2f}")

print("\n2. Custom Layers (Exact same n,k as Auto)")
R_custom = [calculate_tmm(wl, th, layers_custom, 'TM')[0] for th in angles]
print(f"Min R: {np.min(R_custom):.6f} at Angle: {angles[np.argmin(R_custom)]:.2f}")

print("\n3. Custom Layers (Typical user n,k vales: 1.515, 0.12+3.0j, 1.0)")
R_custom_user = [calculate_tmm(wl, th, layers_custom_user, 'TM')[0] for th in angles]
print(f"Min R: {np.min(R_custom_user):.6f} at Angle: {angles[np.argmin(R_custom_user)]:.2f}")
