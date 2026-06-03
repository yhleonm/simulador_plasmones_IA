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

def get_refractive_index(layer_info, wavelength_nm):
    """Devuelve n + ik."""
    material = layer_info['material']
    wl = wavelength_nm
    lam = wl / 1000.0  # micras
    
    if material == "Personalizado (Manual)":
        n = layer_info.get('custom_n', 1.5)
        k = layer_info.get('custom_k', 0.0)
        return n + 1j * k
    
    material_files = {
        "Oro (Au)": "Au_ThinFilm.csv",
        "Plata (Ag)": "Ag_ThinFilm.csv",
        "Cromo (Cr)": "Cr_Johnson.csv",
        "Aluminio (Al)": "Al_Johnson.csv",
        "Titanio (Ti)": "Ti_Johnson.csv",
        "MoS2 (Disulfuro de Molibdeno)": "MoS2.csv",
        "ITO (Óxido de Indio y Estaño)": "ITO.csv"
    }
    
    if material in material_files:
        interpolators = get_interpolator(material_files[material])
        if interpolators:
            f_n, f_k = interpolators
            return float(f_n(wl)) + 1j * float(f_k(wl))

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

def calculate_tmm(wavelength_nm, theta_deg, layers, pol='TM'):
    """Calcula Reflectancia y Transmitancia usando TMM."""
    k0 = 2 * np.pi / wavelength_nm
    theta_rad = np.radians(theta_deg)
    
    ns = [get_refractive_index(L, wavelength_nm) for L in layers]
    ds = [L['d'] for L in layers]
    materials = [L['material'] for L in layers]
    
    n0 = ns[0]
    sin0 = np.sin(theta_rad)
    cos0 = np.lib.scimath.sqrt(1 - sin0**2)
    q0 = n0 / cos0 if pol == 'TM' else n0 * cos0
    
    M = np.identity(2, dtype=complex)
    
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
                sigma_norm = sigma_total * Z0
            M = np.dot(M, np.array([[1.0, 0.0], [sigma_norm, 1.0]], dtype=complex))
        else:
            n, d = ns[i], ds[i]
            cos_theta = np.lib.scimath.sqrt(1 - ((n0 / n) * sin0)**2)
            q = n / cos_theta if pol == 'TM' else n * cos_theta
            delta = k0 * n * d * cos_theta
            M_layer = np.array([[np.cos(delta), (-1j / q) * np.sin(delta)], 
                                [(-1j * q) * np.sin(delta), np.cos(delta)]])
            M = np.dot(M, M_layer)

    nN = ns[-1]
    cosN = np.lib.scimath.sqrt(1 - ((n0 / nN) * sin0)**2)
    qN = nN / cosN if pol == 'TM' else nN * cosN
    
    den = (M[0,0] + M[0,1]*qN)*q0 + (M[1,0] + M[1,1]*qN)
    r = ((M[0,0] + M[0,1]*qN)*q0 - (M[1,0] + M[1,1]*qN)) / den
    R = np.abs(r)**2
    T = (np.real(qN) / np.real(q0)) * np.abs(2*q0 / den)**2
    
    return R, T

def calculate_fwhm(angles, reflectance, res_angle):
    """Calcula el Full Width at Half Maximum (FWHM) del dip de resonancia."""
    # Encontrar el valor base (fuera de la resonancia)
    base_R = np.max(reflectance)
    min_R = np.min(reflectance)
    half_depth = min_R + (base_R - min_R) / 2
    
    # Buscar cruces por el nivel medio
    try:
        # Encontrar los índices donde R cruza half_depth
        idx_res = np.argmin(reflectance)
        
        # Lado izquierdo
        left_idx = np.where(reflectance[:idx_res] > half_depth)[0]
        if len(left_idx) == 0: return 0
        left_angle = angles[left_idx[-1]]
        
        # Lado derecho
        right_idx = np.where(reflectance[idx_res:] > half_depth)[0]
        if len(right_idx) == 0: return 0
        right_angle = angles[idx_res + right_idx[0]]
        
        return abs(right_angle - left_angle)
    except:
        return 0

def calculate_field_profile(wavelength_nm, theta_deg, layers, pol='TM'):
    """Calcula la intensidad del campo eléctrico total (|E|^2) a través de las capas."""
    k0 = 2 * np.pi / wavelength_nm
    theta_rad = np.radians(theta_deg)
    
    ns = [get_refractive_index(L, wavelength_nm) for L in layers]
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
    
    return np.array(z_points), np.array(E_sq)
