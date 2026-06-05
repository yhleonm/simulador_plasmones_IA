import numpy as np
from backend.core.engine import calculate_tmm

def analyze(layers, wl, label, angles=np.linspace(35, 80, 5000)):
    rs = [calculate_tmm(wl, th, layers, 'TM')[0] for th in angles]
    min_idx = np.argmin(rs)
    min_r = rs[min_idx]
    res_angle = angles[min_idx]
    
    # FWHM
    half_max = (1.0 + min_r) / 2.0
    left_side = np.where(np.array(rs[:min_idx]) > half_max)[0]
    right_side = np.where(np.array(rs[min_idx:]) > half_max)[0]
    
    izq_idx = left_side[-1] if len(left_side) > 0 else 0
    der_idx = right_side[0] + min_idx if len(right_side) > 0 else len(rs) - 1
    
    fwhm = angles[der_idx] - angles[izq_idx]
    
    print(f"--- {label} ---")
    print(f"Resonance Angle: {res_angle:.4f}°")
    print(f"Min Reflectance: {min_r:.6f}")
    if der_idx < len(rs)-1 and izq_idx > 0:
        print(f"FWHM: {fwhm:.4f}°")
    else:
        print(f"Unbounded FWHM (no zero/1.0 crossing detected perfectly)")
    print()
    return res_angle, fwhm

# --- Tests ---
wl = 633

print("=== GRUPO 1: MATERIALES GENERALES ===")

layers_1_base = [
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.515, "custom_k": 0.0},
    {"material": "Oro (Au)", "d": 50},
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.333, "custom_k": 0.0}
]
analyze(layers_1_base, 633, "Prueba 1 (Base): Oro puro 50nm")

layers_1 = [
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.515, "custom_k": 0.0},
    {"material": "Plata (Ag)", "d": 35},
    {"material": "Oro (Au)", "d": 15},
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.333, "custom_k": 0.0}
]
analyze(layers_1, 633, "Prueba 1: Bimetálico (Ag 35nm + Au 15nm)")

layers_2_base = [
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.515, "custom_k": 0.0},
    {"material": "Oro (Au)", "d": 45},
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.333, "custom_k": 0.0}
]
analyze(layers_2_base, 633, "Prueba 2 (Base): Oro puro 45nm")

layers_2 = [
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.515, "custom_k": 0.0},
    {"material": "Titanio (Ti)", "d": 2},
    {"material": "Oro (Au)", "d": 45},
    {"material": "MoS2 (Disulfuro de Molibdeno)", "d": 1.5},
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.333, "custom_k": 0.0}
]
analyze(layers_2, 633, "Prueba 2: Biosensor (Ti 2nm + Au 45nm + MoS2 1.5nm)")

layers_3 = [
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.501, "custom_k": 0.0},
    {"material": "ITO (Óxido de Indio y Estaño)", "d": 120},
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.0, "custom_k": 0.0}
]
analyze(layers_3, 1500, "Prueba 3: ITO 120nm a 1500nm", angles=np.linspace(20, 70, 5000))

print("\n=== GRUPO 2: GRAFENO ===")

layers_g1 = [
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.515, "custom_k": 0.0},
    {"material": "Oro (Au)", "d": 50},
    {"material": "Grafeno", "d": 0.335, "custom_layers": 1, "custom_mu": 0.3},
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.333, "custom_k": 0.0}
]
analyze(layers_g1, 633, "G-Prueba 1: 1 Capa de Grafeno (0.335nm)")

layers_g2 = [
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.515, "custom_k": 0.0},
    {"material": "Oro (Au)", "d": 45},
    {"material": "Grafeno", "d": 1.675, "custom_layers": 5, "custom_mu": 0.3},
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.333, "custom_k": 0.0}
]
analyze(layers_g2, 633, "G-Prueba 2: 5 Capas de Grafeno (1.675nm)")

# Sensibilidad (n=1.333 vs 1.338)
layers_g3_bare1 = [
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.515, "custom_k": 0.0},
    {"material": "Oro (Au)", "d": 50},
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.333, "custom_k": 0.0}
]
layers_g3_bare2 = [
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.515, "custom_k": 0.0},
    {"material": "Oro (Au)", "d": 50},
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.338, "custom_k": 0.0}
]
print("G-Prueba 3: Sensibilidad Oro Desnudo:")
th1_bare, _ = analyze(layers_g3_bare1, 633, "Base n=1.333")
th2_bare, _ = analyze(layers_g3_bare2, 633, "Base n=1.338")
shift_bare = th2_bare - th1_bare
print(f"Desplazamiento Bare: {shift_bare:.4f}°")

layers_g3_grap1 = [
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.515, "custom_k": 0.0},
    {"material": "Oro (Au)", "d": 50},
    {"material": "Grafeno", "d": 0.335, "custom_layers": 1, "custom_mu": 0.3},
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.333, "custom_k": 0.0}
]
layers_g3_grap2 = [
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.515, "custom_k": 0.0},
    {"material": "Oro (Au)", "d": 50},
    {"material": "Grafeno", "d": 0.335, "custom_layers": 1, "custom_mu": 0.3},
    {"material": "Personalizado (Manual)", "d": 0, "custom_n": 1.338, "custom_k": 0.0}
]
print("\nG-Prueba 3: Sensibilidad Oro + Grafeno:")
th1_grap, _ = analyze(layers_g3_grap1, 633, "Grafeno n=1.333")
th2_grap, _ = analyze(layers_g3_grap2, 633, "Grafeno n=1.338")
shift_grap = th2_grap - th1_grap
print(f"Desplazamiento Grafeno: {shift_grap:.4f}°")

