from backend.core.engine import get_refractive_index

test_materials = [
    "Vidrio (BK7)", "Sílice (Silica)", "Vidrio Denso (SF10)", "Zafiro Sintético (Al2O3)",
    "PVA", "Glicerina", "TiO2", "ZnO"
]
wl = 633.0

print(f"Indices de Refracción Calculados a {wl} nm:")
print("-" * 40)
for mat in test_materials:
    layer_info = {"material": mat, "d": 0}
    try:
        n_complex = get_refractive_index(layer_info, wl)
        print(f"{mat:25}: {n_complex.real:.4f} + {n_complex.imag:.4f}j")
    except Exception as e:
        print(f"{mat:25}: ERROR - {e}")
