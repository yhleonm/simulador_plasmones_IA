import numpy as np
import pandas as pd
import scipy.constants as const
from scipy.interpolate import interp1d
import os
from functools import lru_cache

# ==========================================
# CONFIGURACIÓN DE BASE DE DATOS
# ==========================================
# Assuming database is at project root
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "database")

@lru_cache(maxsize=32)
def get_interpolator(material_file):
    """Carga y cachea los interpoladores n,k desde un CSV."""
    path = os.path.join(DB_PATH, material_file)
    print(f"DEBUG: Loading material from {path}")
    if not os.path.exists(path):
        print(f"ERROR: Material file not found: {path}")
        return None
    try:
        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]
        
        wl_col = next((c for c in df.columns if c in ['wl', 'wavelength', 'wvl', 'lambda', 'x']), None)
        n_col = next((c for c in df.columns if c in ['n', 'y']), None)
        k_col = next((c for c in df.columns if c in ['k', 'z']), None)

        if not wl_col or not n_col:
            return None

        # Unidades: Micras a Nanómetros
        if df[wl_col].max() < 10.0:
            df[wl_col] = df[wl_col] * 1000.0
            
        f_n = interp1d(df[wl_col], df[n_col], kind='linear', fill_value="extrapolate")
        
        if k_col:
            f_k = interp1d(df[wl_col], df[k_col], kind='linear', fill_value="extrapolate")
        else:
            f_k = lambda x: 0.0

        return f_n, f_k
    except Exception:
        return None

def calculate_graphene_sigma(wavelength_nm, chemical_potential_eV=0.3, temp_K=300, gamma_eV=0.0001):
    """Calcula la conductividad óptica del grafeno usando la fórmula de Kubo."""
    e = const.e
    hbar = const.hbar
    kb = const.k
    c = const.c
    
    omega = 2 * np.pi * c / (wavelength_nm * 1e-9)
    mu = chemical_potential_eV * e
    kT = kb * temp_K
    gamma = gamma_eV * e
    
    # Intrabanda
    term1_intra = (1j * e**2 * kT) / (np.pi * hbar**2 * (omega + 1j * 2 * gamma/hbar))
    term2_intra = (mu / kT) + 2 * np.log(np.exp(-mu / kT) + 1)
    sigma_intra = term1_intra * term2_intra
    
    # Interbanda
    cte_univ = e**2 / (4 * hbar)
    x = (hbar * omega - 2 * mu) / (2 * kT)
    y = (hbar * omega + 2 * mu) / (2 * kT)
    
    real_inter = cte_univ * (0.5 + (1/np.pi) * np.arctan(x))
    arg_log = np.abs((hbar * omega - 2 * mu) / (hbar * omega + 2 * mu))
    imag_inter = - (cte_univ / np.pi) * np.log(arg_log)
    
    sigma_inter = real_inter + 1j * imag_inter
    return sigma_intra + sigma_inter

def get_material_display_name(filename):
    """Mapea nombres de archivos CSV a nombres legibles para el usuario."""
    mapping = {
        "Au_ThinFilm.csv": "Oro (Au)",
        "Au_Johnson.csv": "Oro (Au) - Johnson & Christy",
        "Ag_ThinFilm.csv": "Plata (Ag)",
        "Ag_Johnson.csv": "Plata (Ag) - Johnson & Christy",
        "Cr_Johnson.csv": "Cromo (Cr)",
        "Al_Johnson.csv": "Aluminio (Al)",
        "Ti_Johnson.csv": "Titanio (Ti)",
        "MoS2.csv": "MoS2 (Disulfuro de Molibdeno)",
        "ITO.csv": "ITO (Óxido de Indio y Estaño)",
        "SiO2_Palik.csv": "SiO2 (Dióxido de Silicio) - Palik",
        "Cu_Johnson.csv": "Cobre (Cu) - Johnson & Christy",
        "Si_Green.csv": "Silicio (Si) - Green",
        "SnO2.csv": "Dióxido de Estaño (SnO2)",
        "WS2.csv": "Disulfuro de Tungsteno (WS2)",
    }
    if filename in mapping:
        return mapping[filename]
    if filename.startswith("online_"):
        parts = filename[:-4].split("_")
        if len(parts) >= 4:
            shelf = parts[1]
            book = parts[2]
            page = "_".join(parts[3:])
            return f"{book} ({page}) [Online]"
    name_without_ext = os.path.splitext(filename)[0]
    return name_without_ext.replace("_", " ")

@lru_cache(maxsize=1)
def get_available_materials():
    """Retorna una lista dinámica de todos los materiales disponibles."""
    materials_list = [
        {"name": "Aire / Vacío", "type": "built-in"},
        {"name": "Agua (H2O)", "type": "built-in"},
        {"name": "Vidrio (BK7)", "type": "built-in"},
        {"name": "Sílice (Silica)", "type": "built-in"},
        {"name": "Fluoruro N-F2", "type": "built-in"},
        {"name": "Zafiro Sintético (Al2O3)", "type": "built-in"},
        {"name": "Vidrio Denso (SF10)", "type": "built-in"},
        {"name": "Vidrio N-SF14", "type": "built-in"},
        {"name": "Acrílico SUVT", "type": "built-in"},
        {"name": "Dióxido de Silicio (SiO2)", "type": "built-in"},
        {"name": "PVA", "type": "built-in"},
        {"name": "Glicerina", "type": "built-in"},
        {"name": "Cuarzo", "type": "built-in"},
        {"name": "TiO2", "type": "built-in"},
        {"name": "ZnO", "type": "built-in"},
        {"name": "Grafeno", "type": "built-in"},
        {"name": "Personalizado (Manual)", "type": "built-in"},
    ]
    
    if os.path.exists(DB_PATH):
        try:
            files = [f for f in os.listdir(DB_PATH) if f.endswith('.csv')]
            for f in files:
                name = get_material_display_name(f)
                if not any(m["name"] == name for m in materials_list):
                    materials_list.append({"name": name, "type": "csv", "file": f})
        except Exception as e:
            print(f"Error escaneando base de datos: {e}")
            
    return materials_list

def parse_refractive_index_csv(content_str: str):
    """
    Parsea un string CSV (formato refractiveindex.info o similar) y retorna un DataFrame
    con columnas ['wl', 'n', 'k']. Soporta formatos de bloque doble e individuales.
    Convierte longitudes de onda de micras a nanómetros si es necesario.
    """
    lines = content_str.split('\n')
    
    n_wls, n_vals = [], []
    k_wls, k_vals = [], []
    
    modo_actual = 'n'
    
    for line in lines:
        line = line.strip().lower()
        if not line:
            continue
            
        # Detectar transición de bloque
        if ('wl' in line or 'wavelength' in line or 'lambda' in line) and ('k' in line or 'z' in line or 'extinction' in line):
            modo_actual = 'k'
            continue
        if ('wl' in line or 'wavelength' in line or 'lambda' in line) and ('n' in line or 'y' in line or 'refractive' in line):
            modo_actual = 'n'
            continue
            
        try:
            partes = [p.strip() for p in line.replace(';', ',').replace('\t', ',').split(',')]
            if len(partes) >= 2:
                wl = float(partes[0])
                val = float(partes[1])
                
                if modo_actual == 'n':
                    n_wls.append(wl)
                    n_vals.append(val)
                elif modo_actual == 'k':
                    k_wls.append(wl)
                    k_vals.append(val)
        except ValueError:
            pass
            
    df_n = pd.DataFrame({'wl': n_wls, 'n': n_vals}) if n_wls else pd.DataFrame()
    df_k = pd.DataFrame({'wl': k_wls, 'k': k_vals}) if k_wls else pd.DataFrame()
    
    if df_n.empty and df_k.empty:
        # Intentar parsear como wl,n,k en una sola tabla
        wls, ns, ks = [], [], []
        for line in lines:
            line = line.strip().lower()
            if not line or any(h in line for h in ['wl', 'wavelength', 'lambda', 'n', 'k']):
                continue
            try:
                partes = [p.strip() for p in line.replace(';', ',').replace('\t', ',').split(',')]
                if len(partes) >= 3:
                    wls.append(float(partes[0]))
                    ns.append(float(partes[1]))
                    ks.append(float(partes[2]))
            except ValueError:
                pass
        if wls:
            df_final = pd.DataFrame({'wl': wls, 'n': ns, 'k': ks})
        else:
            raise ValueError("No se encontraron datos de índice de refracción (n o k) válidos en el CSV.")
    else:
        # Convertir micras a nanómetros si es necesario (el formato de refractiveindex.info suele ser micras)
        # Si la longitud de onda máxima es menor a 15, asumimos que está en micras y multiplicamos por 1000.
        if not df_n.empty and df_n['wl'].max() < 15.0:
            df_n['wl'] = df_n['wl'] * 1000.0
        if not df_k.empty and df_k['wl'].max() < 15.0:
            df_k['wl'] = df_k['wl'] * 1000.0
            
        if not df_n.empty and not df_k.empty:
            df_final = pd.merge(df_n, df_k, on='wl', how='outer').sort_values('wl').reset_index(drop=True)
            df_final['n'] = df_final['n'].interpolate(method='linear').bfill().ffill()
            df_final['k'] = df_final['k'].interpolate(method='linear').bfill().ffill()
        elif not df_n.empty:
            df_final = df_n.copy()
            df_final['k'] = 0.0
        else:
            df_final = df_k.copy()
            df_final['n'] = 1.0
            
    return df_final

def get_refractive_index(layer_info, wavelength_nm, temperature_c=20.0):
    """Devuelve n + ik con corrección por temperatura (termo-óptica)."""
    n_base = _get_refractive_index_base(layer_info, wavelength_nm, temperature_c)
    
    material = layer_info.get("material", "")
    dn_dt_map = {
        "Vidrio (BK7)": 3.0e-6,
        "Sílice (Silica)": 1.2e-5,
        "Dióxido de Silicio (SiO2)": 1.0e-5,
        "Agua (H2O)": -8.0e-5,
        "Agua": -8.0e-5,
        "Glicerina": -3.6e-4,
        "Aire / Vacio": -9.0e-7,
        "Aire / Vacío": -9.0e-7,
    }
    
    if material == "Personalizado (Manual)":
        dn_dt = float(layer_info.get("custom_dn_dt", 0.0) or 0.0)
    else:
        dn_dt = dn_dt_map.get(material, 0.0)
        
    delta_t = float(temperature_c) - 20.0
    if delta_t != 0.0 and dn_dt != 0.0:
        n_resolved = (n_base.real + dn_dt * delta_t) + 1j * n_base.imag
    else:
        n_resolved = n_base
        
    delta_n = float(layer_info.get("delta_n", 0.0) or 0.0)
    delta_k = float(layer_info.get("delta_k", 0.0) or 0.0)
    if delta_n != 0.0 or delta_k != 0.0:
        return (n_resolved.real + delta_n) + 1j * (n_resolved.imag + delta_k)
    return n_resolved

def _get_refractive_index_base(layer_info, wavelength_nm, temperature_c=20.0):
    """Lógica base para resolver n + ik a 20°C (con recursión para medios efectivos)."""
    wl = wavelength_nm
    
    # Check if this layer is an effective medium (porous/composite layer)
    if layer_info.get('is_effective_medium', False):
        mat_a = layer_info.get('matrix_material', 'Vidrio (BK7)')
        mat_b = layer_info.get('inclusion_material', 'Aire / Vacio')
        f = layer_info.get('fraction', 0.5)
        model = layer_info.get('model_type', 'bruggeman').lower()
        
        # Resolve components safely without infinite recursion
        info_a = {**layer_info, 'material': mat_a, 'is_effective_medium': False}
        info_b = {**layer_info, 'material': mat_b, 'is_effective_medium': False}
        
        n_a = get_refractive_index(info_a, wavelength_nm, temperature_c)
        n_b = get_refractive_index(info_b, wavelength_nm, temperature_c)
        
        eps_a = n_a ** 2
        eps_b = n_b ** 2
        
        if model == "maxwell-garnett":
            # Maxwell-Garnett
            num = eps_b * (1.0 + 2.0 * f) + 2.0 * eps_a * (1.0 - f)
            den = eps_b * (1.0 - f) + eps_a * (2.0 + f)
            eps_eff = eps_a * (num / den)
            return np.lib.scimath.sqrt(eps_eff)
        else:
            # Bruggeman
            B = (2.0 - 3.0 * f) * eps_a + (3.0 * f - 1.0) * eps_b
            val_sqrt = np.lib.scimath.sqrt(B**2 + 8.0 * eps_a * eps_b)
            eps1 = (B + val_sqrt) / 4.0
            eps2 = (B - val_sqrt) / 4.0
            eps_eff = eps1 if eps1.real >= 0 else eps2
            return np.lib.scimath.sqrt(eps_eff)

    material = layer_info['material']
    lam = wl / 1000.0  # micras
    
    if material == "Personalizado (Manual)":
        n = layer_info.get('custom_n', 1.5)
        k = layer_info.get('custom_k', 0.0)
        return n + 1j * k
        
    # 1. Buscar en materiales dinámicos (CSVs en database/)
    materials = get_available_materials()
    for m in materials:
        if m["type"] == "csv" and m["name"] == material:
            interpolators = get_interpolator(m["file"])
            if interpolators:
                f_n, f_k = interpolators
                return float(f_n(wl)) + 1j * float(f_k(wl))

    # 2. Fórmulas analíticas o valores fijos si no se encuentra en CSV
    sellmeier_params = {
        "Vidrio (BK7)": (1.03961212, 2.31792344E-1, 1.01046945, 6.00069867E-3, 2.00179144E-2, 103.560653),
        "Sílice (Silica)": (0.6961663, 0.4079426, 0.8974794, 4.6791E-3, 1.35121E-2, 97.934003),
        "Fluoruro N-F2": (1.39757037, 1.59201403E-1, 1.2686543, 9.95906143E-3, 5.46931752E-2, 119.2483460),
        "Zafiro Sintético (Al2O3)": (1.4313493, 0.65054713, 5.3414021, 0.00527993, 0.0142383, 325.01783),
        "Vidrio Denso (SF10)": (1.62153902, 0.256287842, 1.64447552, 0.0122241457, 0.0595736775, 147.468793),
        "Vidrio N-SF14": (1.69022361, 0.288870052, 1.704518700, 0.01305121130, 0.0613691880, 149.5176890),
        "Acrílico SUVT": (0.59411, 0.59423, 0, 0.010837, 0.0099968, 0),
        "Dióxido de Silicio (SiO2)": (0.6961663, 0.4079426, 0.8974794, 0.0684043**2, 0.1162414**2, 9.896161**2)
    }

    if material in sellmeier_params:
        B1, B2, B3, C1, C2, C3 = sellmeier_params[material]
        n_sq = 1 + (B1 * lam**2)/(lam**2 - C1) + (B2 * lam**2)/(lam**2 - C2) + (B3 * lam**2)/(lam**2 - C3)
        return np.sqrt(n_sq) + 0j

    if material == "PVA":
        return (1.460 + (0.00665 / lam**2)) + 0j
    elif material == "Glicerina":
        return (1.45797 + (0.00598 / lam**2) - (0.00036 / lam**4)) + 0j
    elif material == "Cuarzo":
        return np.sqrt(2.356764950 - 1.139969240E-2 * lam**2 + 1.087416560E-2 / lam**2 + 3.320669140E-5 / lam**4 + 1.086093460E-5 / lam**6) + 0j
    elif material == "TiO2":
        E_i = (4.13566743e-15 * 3e8) / (lam * 1e-6)
        return np.sqrt(1 + (101 / (6.2**2 - E_i**2 - 1j * 1.2 * E_i)))
    elif material == "ZnO":
        omega = 2 * np.pi * 299792458 / (lam * 1e-6)
        wp, gamma = 2e15, 1.5e14
        e_ZnO = 3.4 - (wp**2) / (omega**2 + gamma**2) + 1j * (gamma * wp**2) / ((omega**2 + gamma**2) * omega)
        return np.sqrt(e_ZnO)
    elif material == "Grafeno":
        sigma = calculate_graphene_sigma(wl, layer_info.get('custom_mu', 0.3))
        d_g = layer_info.get('d', 0.335) * 1e-9
        omega = 2 * np.pi * const.c / (wl * 1e-9)
        eps_eff = 1.0 + (1j * sigma) / (omega * const.epsilon_0 * d_g)
        return np.sqrt(eps_eff)
    elif material == "Aire / Vacío":
        return 1.0 + 0j
    elif material in ["Agua (H2O)", "Agua"]:
        return 1.333 + 0j

    return 1.5 + 0j

def calculate_tmm(wavelength_nm, theta_deg, layers, pol='TM', return_coefficient=False, temperature_c=20.0):
    """Calcula Reflectancia y Transmitancia usando TMM con ajuste termo-óptico (soportando theta_deg escalar o array)."""
    k0 = 2 * np.pi / wavelength_nm
    is_scalar = np.isscalar(theta_deg)
    theta_deg_arr = np.atleast_1d(theta_deg)
    theta_rad = np.radians(theta_deg_arr)
    
    ns = [get_refractive_index(L, wavelength_nm, temperature_c) for L in layers]
    ds = [L['d'] for L in layers]
    materials = [L['material'] for L in layers]
    
    n0 = ns[0]
    sin0 = np.sin(theta_rad)
    cos0 = np.lib.scimath.sqrt(1 - sin0**2)
    q0 = n0 / cos0 if pol == 'TM' else n0 * cos0
    
    N_angles = len(theta_deg_arr)
    M = np.zeros((N_angles, 2, 2), dtype=complex)
    M[:, 0, 0] = 1.0
    M[:, 1, 1] = 1.0
    
    for i in range(1, len(ns) - 1):
        if materials[i] == "Grafeno":
            n_capas = int(layers[i].get('custom_layers', 1))
            mu_c = layers[i].get('custom_mu', 0.3) 
            sigma_total = n_capas * calculate_graphene_sigma(wavelength_nm, mu_c)
            Z0 = 376.73
            if pol == 'TM':
                n_prev = ns[i-1]
                cos_adj = np.lib.scimath.sqrt(1 - ((n0 / n_prev) * sin0)**2)
                sigma_norm = sigma_total * Z0 / cos_adj
            else:
                sigma_norm = np.full(N_angles, sigma_total * Z0, dtype=complex)
            
            M[:, 0, 0] += M[:, 0, 1] * sigma_norm
            M[:, 1, 0] += M[:, 1, 1] * sigma_norm
        else:
            n, d = ns[i], ds[i]
            cos_theta = np.lib.scimath.sqrt(1 - ((n0 / n) * sin0)**2)
            q = n / cos_theta if pol == 'TM' else n * cos_theta
            delta = k0 * n * d * cos_theta
            
            cos_d = np.cos(delta)
            sin_d = np.sin(delta)
            
            B00 = cos_d
            B01 = (-1j / q) * sin_d
            B10 = (-1j * q) * sin_d
            B11 = cos_d
            
            M00_new = M[:, 0, 0] * B00 + M[:, 0, 1] * B10
            M01_new = M[:, 0, 0] * B01 + M[:, 0, 1] * B11
            M10_new = M[:, 1, 0] * B00 + M[:, 1, 1] * B10
            M11_new = M[:, 1, 0] * B01 + M[:, 1, 1] * B11
            
            M[:, 0, 0] = M00_new
            M[:, 0, 1] = M01_new
            M[:, 1, 0] = M10_new
            M[:, 1, 1] = M11_new

    nN = ns[-1]
    cosN = np.lib.scimath.sqrt(1 - ((n0 / nN) * sin0)**2)
    qN = nN / cosN if pol == 'TM' else nN * cosN
    
    den = (M[:, 0, 0] + M[:, 0, 1]*qN)*q0 + (M[:, 1, 0] + M[:, 1, 1]*qN)
    r = ((M[:, 0, 0] + M[:, 0, 1]*qN)*q0 - (M[:, 1, 0] + M[:, 1, 1]*qN)) / den
    R = np.abs(r)**2
    T = (np.real(qN) / np.real(q0)) * np.abs(2*q0 / den)**2
    
    # Guardrails to enforce physical energy conservation (R + T <= 1.0)
    kx = np.real(n0) * np.sin(theta_rad)
    is_evanescent = (np.abs(np.imag(nN)) < 1e-9) & (kx >= np.real(nN) - 1e-10)
    T = np.where(is_evanescent, 0.0, np.clip(T, 0.0, 1.0 - R))
    
    if is_scalar:
        R_val = float(R[0])
        T_val = float(T[0])
        if return_coefficient:
            r_val = complex(r[0])
            return R_val, T_val, r_val
        return R_val, T_val
    else:
        if return_coefficient:
            return R, T, r
        return R, T

def calculate_fwhm(angles, reflectance, res_angle):
    """Calcula el Full Width at Half Maximum (FWHM) del dip de resonancia."""
    # Encontrar el valor base (fuera de la resonancia)
    base_R = np.max(reflectance)
    min_R = np.min(reflectance)
    
    # Buscar cruces por el nivel medio
    try:
        # Encontrar los índices donde R cruza half_depth
        idx_res = np.argmin(reflectance)
        
        left_curve = reflectance[:idx_res]
        right_curve = reflectance[idx_res:]
        
        # Umbrales independientes para cada lado para soportar asimetrías y límites de barrido (ej. espectral)
        max_left = np.max(left_curve) if len(left_curve) > 0 else base_R
        left_half = min_R + (max_left - min_R) / 2.0
        
        max_right = np.max(right_curve) if len(right_curve) > 0 else base_R
        right_half = min_R + (max_right - min_R) / 2.0
        
        # Buscar cruces por el nivel medio en cada lado
        left_idx = np.where(left_curve > left_half)[0]
        right_idx = np.where(right_curve > right_half)[0]
        
        # Caída de respaldo a umbral global si alguno de los lados no cruza
        if len(left_idx) == 0 or len(right_idx) == 0:
            half_depth = min_R + (base_R - min_R) / 2.0
            left_idx = np.where(left_curve > half_depth)[0]
            right_idx = np.where(right_curve > half_depth)[0]
            if len(left_idx) == 0 or len(right_idx) == 0:
                return 0.0
                
        left_angle = angles[left_idx[-1]]
        right_angle = angles[idx_res + right_idx[0]]
        
        return abs(right_angle - left_angle)
    except:
        return 0.0

def calculate_field_profile(wavelength_nm, theta_deg, layers, pol='TM', return_complex=False, temperature_c=20.0):
    """Calcula la intensidad del campo eléctrico total (|E|^2) a través de las capas con ajuste térmico."""
    k0 = 2 * np.pi / wavelength_nm
    theta_rad = np.radians(theta_deg)
    
    ns = [get_refractive_index(L, wavelength_nm, temperature_c) for L in layers]
    ds = [L['d'] for L in layers]
    n0 = ns[0]
    sin0 = np.sin(theta_rad)
    
    # Coeficiente de Fresnel y propagación
    def get_layer_matrix(n, d, pol, n0, sin0, k0):
        cos_theta = np.lib.scimath.sqrt(1 - ((n0 / n) * sin0)**2)
        q = n / cos_theta if pol == 'TM' else n * cos_theta
        delta = k0 * n * d * cos_theta
        M = np.array([[np.cos(delta), (-1j / q) * np.sin(delta)], 
                      [(-1j * q) * np.sin(delta), np.cos(delta)]])
        return M, q, cos_theta

    # Paso 1: TMM total para obtener r
    M_total = np.identity(2, dtype=complex)
    qs = []
    cos_thetas = []
    
    # Incidente (Capa 0)
    q0 = n0 / np.cos(theta_rad) if pol == 'TM' else n0 * np.cos(theta_rad)
    qs.append(q0)
    cos_thetas.append(np.cos(theta_rad))
    
    for i in range(1, len(ns)-1):
        Mi, qi, ci = get_layer_matrix(ns[i], ds[i], pol, n0, sin0, k0)
        M_total = np.dot(M_total, Mi)
        qs.append(qi)
        cos_thetas.append(ci)
        
    nN = ns[-1]
    cosN = np.lib.scimath.sqrt(1 - ((n0 / nN) * sin0)**2)
    qN = nN / cosN if pol == 'TM' else nN * cosN
    qs.append(qN)
    cos_thetas.append(cosN)
    
    den = (M_total[0,0] + M_total[0,1]*qN)*q0 + (M_total[1,0] + M_total[1,1]*qN)
    r = ((M_total[0,0] + M_total[0,1]*qN)*q0 - (M_total[1,0] + M_total[1,1]*qN)) / den
    
    # Paso 2: Propagación del campo
    z_points = []
    E_sq = []
    E_complex = []
    
    # Inicialización en la interfaz 0/1
    # Vector de transferencia [E, H]
    # E_total = E_inc + E_ref = 1 + r
    # H_total = q0 * (E_inc - E_ref) = q0 * (1 - r)
    current_EH = np.array([[1 + r], [q0 * (1 - r)]])
    
    # Prisma (Capa 0) - propagando hacia atrás
    z_pre = np.linspace(-150, 0, 100)
    kz0 = k0 * n0 * cos_thetas[0]
    # E_x(z) = E_inc * exp(ikz) + E_ref * exp(-ikz)
    E_prisma = np.exp(1j * kz0 * z_pre) + r * np.exp(-1j * kz0 * z_pre)
    z_points.extend(z_pre.tolist())
    E_sq.extend(np.abs(E_prisma)**2)
    E_complex.extend(E_prisma.tolist())
    
    current_z = 0
    for i in range(1, len(ns)-1):
        z_layer = np.linspace(0, ds[i], 100)
        qi = qs[i]
        kzi = k0 * ns[i] * cos_thetas[i]
        
        # Componentes A y B de la onda en la capa: E(z) = A*exp(ikz) + B*exp(-ikz)
        # En z=0 (inicio de capa): E(0) = A+B, H(0) = qi(A-B)
        E0, H0 = current_EH[0,0], current_EH[1,0]
        A = 0.5 * (E0 + H0/qi)
        B = 0.5 * (E0 - H0/qi)
        
        Ei = A * np.exp(1j * kzi * z_layer) + B * np.exp(-1j * kzi * z_layer)
        
        z_points.extend((current_z + z_layer).tolist())
        E_sq.extend(np.abs(Ei)**2)
        E_complex.extend(Ei.tolist())
        
        # Mover al final de la capa para la siguiente interfaz
        Mi, _, _ = get_layer_matrix(ns[i], ds[i], pol, n0, sin0, k0)
        current_EH = np.dot(Mi, current_EH)
        current_z += ds[i]
        
    # Salida (Capa N)
    z_post = np.linspace(0, 300, 150)
    kzN = k0 * ns[-1] * cos_thetas[-1]
    # Solo onda transmitida: E(z) = E_trans * exp(ikz)
    E_trans = current_EH[0,0]
    EN = E_trans * np.exp(1j * kzN * z_post)
    
    z_points.extend((current_z + z_post).tolist())
    E_sq.extend(np.abs(EN)**2)
    E_complex.extend(EN.tolist())
    
    if return_complex:
        return np.array(z_points), np.array(E_sq), np.array(E_complex)
    return np.array(z_points), np.array(E_sq)


# ==========================================
# CONECTOR ONLINE CON REFRACTIVEINDEX.INFO
# ==========================================

def _evaluate_dispersion_formula(formula_id: int, coefficients: list, wl_um: np.ndarray):
    """Computa el índice de refracción 'n' a partir de una fórmula de dispersión."""
    wl = np.asarray(wl_um, dtype=float)
    # Rellenar con ceros para evitar errores de índice
    C = list(coefficients) + [0.0] * 20
    
    if formula_id == 1:  # Sellmeier
        nsq = 1 + C[0]
        for i in range(1, len(coefficients), 2):
            nsq = nsq + C[i] * wl**2 / (wl**2 - C[i+1]**2)
        return np.sqrt(nsq)
        
    elif formula_id == 2:  # Sellmeier-2
        nsq = 1 + C[0]
        for i in range(1, len(coefficients), 2):
            nsq = nsq + C[i] * wl**2 / (wl**2 - C[i+1])
        return np.sqrt(nsq)
        
    elif formula_id == 3:  # Polynomial
        nsq = C[0]
        for i in range(1, len(coefficients), 2):
            nsq = nsq + C[i] * wl**C[i+1]
        return np.sqrt(nsq)
        
    elif formula_id == 4:  # RefractiveIndex.INFO
        nsq = C[0]
        for i in range(1, min(8, len(coefficients)), 4):
            nsq = nsq + C[i] * wl**C[i+1] / (wl**2 - C[i+2]**C[i+3])
        if len(coefficients) > 9:
            for i in range(9, len(coefficients), 2):
                nsq = nsq + C[i] * wl**C[i+1]
        return np.sqrt(nsq)
        
    elif formula_id == 5:  # Cauchy
        n = C[0]
        for i in range(1, len(coefficients), 2):
            n = n + C[i] * wl**C[i+1]
        return n
        
    elif formula_id == 6:  # Gases
        n = 1 + C[0]
        for i in range(1, len(coefficients), 2):
            n = n + C[i] / (C[i+1] - wl**(-2))
        return n
        
    elif formula_id == 7:  # Herzberger
        n = C[0] + C[1]/(wl**2 - 0.028) + C[2]/(wl**2 - 0.028)**2
        for i in range(3, len(coefficients)):
            n = n + C[i] * wl**(2 * (i - 2))
        return n
        
    elif formula_id == 8:  # Retro
        tmp = C[0] + C[1]*wl**2/(wl**2 - C[2]) + C[3]*wl**2
        return np.sqrt((2*tmp + 1)/(1 - tmp))
        
    elif formula_id == 9:  # Exotic
        return np.sqrt(C[0] + C[1]/(wl**2 - C[2]) + C[3]*(wl - C[4])/((wl - C[4])**2 + C[5]))
        
    else:
        raise ValueError(f"Fórmula tipo {formula_id} no soportada.")

def _parse_tabulated_block(data_str: str):
    rows = data_str.strip().split('\n')
    wls, col1, col2 = [], [], []
    for r in rows:
        parts = [p.strip() for p in r.replace(';', ',').replace('\t', ',').split(',') if p.strip()]
        if not parts or parts[0].startswith('#'):
            continue
        try:
            if len(parts) == 1:
                parts = parts[0].split()
            if len(parts) >= 2:
                wls.append(float(parts[0]))
                col1.append(float(parts[1]))
                if len(parts) >= 3:
                    col2.append(float(parts[2]))
                else:
                    col2.append(0.0)
        except ValueError:
            pass
    return np.array(wls), np.array(col1), np.array(col2)

def import_material_from_url(url: str):
    """Descarga un archivo YAML desde refractiveindex.info resolviendo la ruta con catalog-nk, y lo guarda como CSV."""
    import urllib.parse
    import urllib.request
    import yaml
    import re
    
    # 1. Parsear la URL
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    
    shelf_q = params.get('shelf', [None])[0]
    book_q = params.get('book', [None])[0]
    page_q = params.get('page', [None])[0]
    
    if not shelf_q or not book_q or not page_q:
        raise ValueError("La URL debe contener los parámetros 'shelf', 'book' y 'page'.")
        
    # Sanitizar nombres de consulta
    shelf_q = shelf_q.strip()
    book_q = book_q.strip()
    page_q = page_q.strip()
    
    # 2. Cargar el catálogo y resolver la ruta relativa
    records = _get_catalog_records()
    
    relative_path = None
    # Intento 1: Coincidencia exacta insensible a mayúsculas
    for r in records:
        if (r['shelf'].lower() == shelf_q.lower() and 
            r['book'].lower() == book_q.lower() and 
            r['page'].lower() == page_q.lower()):
            relative_path = r['path']
            break
            
    # Intento 2: Coincidencia fuzzy en book y shelf (page exacta)
    if not relative_path:
        candidates = []
        for r in records:
            if r['page'].lower() != page_q.lower():
                continue
            score = 0
            if book_q.lower() in r['book'].lower() or r['book'].lower() in book_q.lower():
                score += 10
            if shelf_q.lower() in r['shelf'].lower() or r['shelf'].lower() in shelf_q.lower():
                score += 5
            candidates.append((score, r['path']))
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            relative_path = candidates[0][1]
            
    # Intento 3: Coincidencia fuzzy en page
    if not relative_path:
        candidates = []
        for r in records:
            if page_q.lower() in r['page'].lower() or r['page'].lower() in page_q.lower():
                score = 0
                if book_q.lower() in r['book'].lower() or r['book'].lower() in book_q.lower():
                    score += 10
                if shelf_q.lower() in r['shelf'].lower() or r['shelf'].lower() in shelf_q.lower():
                    score += 5
                candidates.append((score, r['path']))
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            relative_path = candidates[0][1]
            
    if not relative_path:
        raise ValueError(f"No se pudo encontrar ningún material en el catálogo para la combinación: Shelf={shelf_q}, Book={book_q}, Page={page_q}")
        
    # 3. Descargar el archivo YAML de GitHub raw
    github_raw_url = f"https://raw.githubusercontent.com/polyanskiy/refractiveindex.info-database/master/database/data/{relative_path}"
    
    try:
        req = urllib.request.Request(
            github_raw_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response:
            yaml_content = response.read().decode('utf-8')
    except Exception as e:
        raise RuntimeError(f"Error descargando el material desde GitHub ({github_raw_url}): {str(e)}")
        
    # 4. Parsear el YAML
    try:
        data_dict = yaml.safe_load(yaml_content)
    except Exception as e:
        raise ValueError(f"Error parseando el archivo YAML: {str(e)}")
        
    data_list = data_dict.get('DATA', [])
    if not data_list:
        raise ValueError("El archivo YAML no contiene la sección 'DATA'.")
        
    # 5. Analizar bloques de datos
    tabulated_n_block = None
    tabulated_k_block = None
    tabulated_nk_block = None
    formula_block = None
    
    for block in data_list:
        block_type = block.get('type', '').lower().strip()
        if 'tabulated nk' in block_type:
            tabulated_nk_block = block
        elif 'tabulated n' in block_type:
            tabulated_n_block = block
        elif 'tabulated k' in block_type:
            tabulated_k_block = block
        elif 'formula' in block_type:
            formula_block = block
            
    # 6. Generar la tabla de datos wl (nm), n, k
    if tabulated_nk_block:
        wl_um, n_vals, k_vals = _parse_tabulated_block(tabulated_nk_block['data'])
    elif tabulated_n_block and tabulated_k_block:
        wl_n, n_vals, _ = _parse_tabulated_block(tabulated_n_block['data'])
        wl_k, k_vals, _ = _parse_tabulated_block(tabulated_k_block['data'])
        
        wl_um = np.unique(np.concatenate([wl_n, wl_k]))
        n_vals = np.interp(wl_um, wl_n, n_vals)
        k_vals = np.interp(wl_um, wl_k, k_vals)
    elif tabulated_n_block and not formula_block:
        wl_um, n_vals, _ = _parse_tabulated_block(tabulated_n_block['data'])
        k_vals = np.zeros_like(n_vals)
    elif tabulated_k_block and not formula_block:
        wl_um, k_vals, _ = _parse_tabulated_block(tabulated_k_block['data'])
        n_vals = np.ones_like(k_vals)
    elif formula_block:
        range_str = formula_block.get('wavelength_range', '0.3 2.0')
        parts = range_str.split()
        wl_min = float(parts[0])
        wl_max = float(parts[1])
        
        if tabulated_k_block:
            wl_um, k_vals, _ = _parse_tabulated_block(tabulated_k_block['data'])
            valid_mask = (wl_um >= wl_min) & (wl_um <= wl_max)
            if np.sum(valid_mask) > 0:
                wl_um = wl_um[valid_mask]
                k_vals = k_vals[valid_mask]
            else:
                wl_um = np.linspace(wl_min, wl_max, 300)
                k_vals = np.zeros_like(wl_um)
        else:
            wl_um = np.linspace(wl_min, wl_max, 300)
            k_vals = np.zeros_like(wl_um)
            
        coefs = [float(x) for x in formula_block.get('coefficients', '').split()]
        formula_type_str = formula_block.get('type', '')
        formula_id = int(re.search(r'\d+', formula_type_str).group())
        
        n_vals = _evaluate_dispersion_formula(formula_id, coefs, wl_um)
    else:
        raise ValueError("El archivo de material no contiene un formato de datos reconocible (fórmulas o tablas).")
        
    # 7. Guardar en formato CSV
    wl_nm = wl_um * 1000.0
    df_len = len(wl_nm)
    
    if not isinstance(n_vals, np.ndarray) or len(n_vals) != df_len:
        n_vals = np.full(df_len, n_vals)
    if not isinstance(k_vals, np.ndarray) or len(k_vals) != df_len:
        k_vals = np.full(df_len, k_vals)
        
    import pandas as pd
    df = pd.DataFrame({
        'wl': wl_nm,
        'n': n_vals,
        'k': k_vals
    })
    
    df = df.sort_values('wl').reset_index(drop=True)
    
    # Sanitizar nombres para el archivo CSV local
    safe_shelf = "".join(c for c in shelf_q if c.isalnum() or c in ('-', '_')).strip()
    safe_book = "".join(c for c in book_q if c.isalnum() or c in ('-', '_')).strip()
    safe_page = "".join(c for c in page_q if c.isalnum() or c in ('-', '_')).strip()
    
    safe_filename = f"online_{safe_shelf}_{safe_book}_{safe_page}.csv"
    dest_path = os.path.join(DB_PATH, safe_filename)
    
    os.makedirs(DB_PATH, exist_ok=True)
    df.to_csv(dest_path, index=False)
    
    get_available_materials.cache_clear()
    
    return {
        "filename": safe_filename,
        "display_name": f"{book_q} ({page_q}) [Online]",
        "path": dest_path
    }

_catalog_records_cache = None

def _get_catalog_records():
    global _catalog_records_cache
    if _catalog_records_cache is not None:
        return _catalog_records_cache
        
    import urllib.request
    import yaml
    
    url = "https://raw.githubusercontent.com/polyanskiy/refractiveindex.info-database/master/database/catalog-nk.yml"
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8')
        catalog = yaml.safe_load(content)
        
        records = []
        for shelf in catalog:
            if "DIVIDER" in shelf:
                continue
            shelf_name = shelf.get("SHELF")
            for book_entry in shelf.get("content", []):
                if "DIVIDER" in book_entry:
                    continue
                book_name = book_entry.get("BOOK")
                for page_entry in book_entry.get("content", []):
                    if "DIVIDER" in page_entry:
                        continue
                    page_name = page_entry.get("PAGE")
                    data_rel = page_entry.get("data")
                    if data_rel:
                        records.append({
                            'shelf': shelf_name,
                            'book': book_name,
                            'page': page_name,
                            'path': data_rel
                        })
        _catalog_records_cache = records
        return records
    except Exception as e:
        raise RuntimeError(f"Error cargando catálogo-nk desde GitHub: {str(e)}")
