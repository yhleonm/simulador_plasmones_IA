import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go  
import torch
from scipy.interpolate import interp1d
import matplotlib.colors as mcolors
from scipy.optimize import minimize 
from scipy.optimize import minimize_scalar 
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler 
import scipy.constants as const  
import os

# ==========================================
# CONFIGURACIÓN DE BASE DE DATOS
# ==========================================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database")

@st.cache_resource
def get_interpolator(material_file):
    """Carga y cachea los interpoladores n,k desde un CSV (Corregido para nanómetros)."""
    path = os.path.join(DB_PATH, material_file)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        # Normalizar nombres de columnas (minúsculas y sin espacios)
        df.columns = [c.strip().lower() for c in df.columns]
        
        # Detectar columnas dinámicamente
        wl_col = next((c for c in df.columns if c in ['wl', 'wavelength', 'wvl', 'lambda', 'x']), None)
        n_col = next((c for c in df.columns if c in ['n', 'y']), None)
        k_col = next((c for c in df.columns if c in ['k', 'z']), None)

        if not wl_col or not n_col:
            st.error(f"Formato inválido en {material_file}. Se requieren columnas de longitud de onda y 'n'.")
            return None

        # --- CORRECCIÓN VITAL DE UNIDADES ---
        # Si el valor máximo es menor a 10, significa que está en micras.
        # Lo multiplicamos por 1000 para que trabaje en nanómetros (como el resto de tu app).
        if df[wl_col].max() < 10.0:
            df[wl_col] = df[wl_col] * 1000.0
            
        # Interpolación lineal para mayor robustez ante pocos puntos
        f_n = interp1d(df[wl_col], df[n_col], kind='linear', fill_value="extrapolate")
        
        if k_col:
            f_k = interp1d(df[wl_col], df[k_col], kind='linear', fill_value="extrapolate")
        else:
            f_k = lambda x: 0.0

        return f_n, f_k
    except Exception as e:
        st.error(f"Error cargando {material_file}: {e}")
        return None

# ==========================================
# 0. MODELOS DE MATERIALES AVANZADOS (GRAFENO)
# ==========================================

def calculate_graphene_sigma(wavelength_nm, chemical_potential_eV=0.3, temp_K=300, gamma_eV=0.0001):
    """
    Calcula la conductividad óptica del grafeno usando la fórmula de Kubo.
    Suma de intrabanda y interbanda.
    
    Parámetros:
    - wavelength_nm: Longitud de onda en nm
    - chemical_potential_eV: Potencial químico (Nivel de Fermi) en eV. Default: 0.3 eV (~5x10^12 cm^-2 dopaje)
    - temp_K: Temperatura en Kelvin. Default: 300 K
    - gamma_eV: Tasa de dispersión (scattering rate) en eV. Relacionado con la movilidad.
    """
    
    # Constantes Físicas
    e = const.e             # Carga elemental
    hbar = const.hbar       # Planck reducida
    kb = const.k            # Boltzmann
    c = const.c             # Velocidad luz
    
    # Conversión de unidades
    omega = 2 * np.pi * c / (wavelength_nm * 1e-9)  # Frecuencia angular (rad/s)
    mu = chemical_potential_eV * e                  # Potencial químico en Joules
    kT = kb * temp_K                                # Energía térmica en Joules
    gamma = gamma_eV * e                            # Scattering en Joules
    
    # --- TÉRMINO INTRABANDA (Drude-like) ---
    # sigma_intra = (i * e^2 * kT / (pi * hbar^2 * (omega + i*2*gamma))) * [ mu/kT + 2*ln(exp(-mu/kT) + 1) ]
    
    term1_intra = (1j * e**2 * kT) / (np.pi * hbar**2 * (omega + 1j * 2 * gamma/hbar))
    term2_intra = (mu / kT) + 2 * np.log(np.exp(-mu / kT) + 1)
    sigma_intra = term1_intra * term2_intra
    
    # --- TÉRMINO INTERBANDA ---
    # sigma_inter = (e^2 / 4*hbar) * [ 0.5 + (1/pi)*arctan((hbar*omega - 2*mu)/(2*kT)) - (i/2*pi)*ln( ... ) ]
    
    # Aproximación común para T=300K (Step function suavizada)
    # sigma_inter ~= (e^2 / 4*hbar) * [ G(hbar*omega/2) + i * 4 * omega / (pi * ... integral ... ) ]
    # Usaremos la forma completa simplificada:
    
    cte_univ = e**2 / (4 * hbar)
    x = (hbar * omega - 2 * mu) / (2 * kT)
    y = (hbar * omega + 2 * mu) / (2 * kT)
    
    # Parte Real (Absorción interbanda - Step function)
    real_inter = cte_univ * (0.5 + (1/np.pi) * np.arctan(x))
    
    # Parte Imaginaria (Logaritmo)
    # Evitar división por cero en logaritmo
    arg_log = np.abs((hbar * omega - 2 * mu) / (hbar * omega + 2 * mu))
    imag_inter = - (cte_univ / np.pi) * np.log(arg_log)
    
    sigma_inter = real_inter + 1j * imag_inter
    
    # Conductividad Total
    sigma_total = sigma_intra + sigma_inter
    
    return sigma_total

# ==========================================
# 1. SIMULACIÓN DE BASE DE DATOS (REFRACTIVE INDEX)
# ==========================================
#

def get_refractive_index(layer_info, wavelength_nm):
    """
    Devuelve n + ik. 
    Recibe 'layer_info' que es el diccionario completo de la capa 
    (ej: {'material': 'Oro', 'd': 50, 'custom_n': 1.5, ...})
    """
    material = layer_info['material']
    wl = wavelength_nm
    lam = wl / 1000.0  # micras
    
    # 0. Lógica para Material Personalizado
    if material == "Personalizado (Manual)":
        n = layer_info.get('custom_n', 1.5)
        k = layer_info.get('custom_k', 0.0)
        return n + 1j * k
    
    # 1. Base de Datos CSV (Especialmente Metales y Semimetales)
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
        filename = material_files[material]
        interpolators = get_interpolator(filename)
        if interpolators:
            f_n, f_k = interpolators
            try:
                n_val = float(f_n(wavelength_nm))
                k_val = float(f_k(wavelength_nm))
                return n_val + 1j * k_val
            except Exception:
                pass # Si falla, intenta respaldo tabular

    # 2. Materiales Analíticos (Ecuación de Sellmeier)
    sellmeier_params = {
        # Format: (B1, B2, B3, C1, C2, C3)
        "Vidrio (BK7)": (1.03961212, 2.31792344E-1, 1.01046945, 6.00069867E-3, 2.00179144E-2, 103.560653),
        "Sílice (Silica)": (0.6961663, 0.4079426, 0.8974794, 4.6791E-3, 1.35121E-2, 97.934003),
        "Fluoruro N-F2": (1.39757037, 1.59201403E-1, 1.2686543, 9.95906143E-3, 5.46931752E-2, 119.2483460),
        "Zafiro Sintético (Al2O3)": (1.4313493, 0.65054713, 5.3414021, 0.00527993, 0.0142383, 325.01783),
        "Vidrio Denso (SF10)": (1.62153902, 0.256287842, 1.64447552, 0.0122241457, 0.0595736775, 147.468793),
        "Vidrio N-SF14": (1.69022361, 0.288870052, 1.704518700, 0.01305121130, 0.0613691880, 149.5176890),
        "Acrílico SUVT": (0.59411, 0.59423, 0, 0.010837, 0.0099968, 0),
        "Dióxido de Silicio (SiO2)": (0.6961663, 0.4079426, 0.8974794, 0.0684043**2, 0.1162414**2, 9.896161**2) # Equivalente Silica
    }

    if material in sellmeier_params:
        B1, B2, B3, C1, C2, C3 = sellmeier_params[material]
        n_sq = 1 + (B1 * lam**2)/(lam**2 - C1) + (B2 * lam**2)/(lam**2 - C2) + (B3 * lam**2)/(lam**2 - C3)
        return np.sqrt(n_sq) + 0j

    # 3. Modelos Polinomiales/Cauchy Extendidos (Líquidos y Polímeros)
    if material == "PVA":
        n = 1.460 + (0.00665 / lam**2)
        return n + 0j
    elif material == "Glicerina":
        n = 1.45797 + (0.00598 / lam**2) - (0.00036 / lam**4)
        return n + 0j
    elif material == "Cuarzo":
        n = np.sqrt(2.356764950 - 1.139969240E-2 * lam**2 + 1.087416560E-2 / lam**2 + 3.320669140E-5 / lam**4 + 1.086093460E-5 / lam**6)
        return n + 0j

    # 4. Formalismo Drude-Lorentz (Óxidos)
    if material == "TiO2":
        E_i = (4.13566743e-15 * 3e8) / (lam * 1e-6) # Energía en eV
        e_TiO2 = 1 + (101 / (6.2**2 - E_i**2 - 1j * 1.2 * E_i))
        return np.sqrt(e_TiO2)
    elif material == "ZnO":
        omega = 2 * np.pi * 299792458 / (lam * 1e-6)
        wp = 2e15
        gamma = 1.5e14
        e_ZnO = 3.4 - (wp**2) / (omega**2 + gamma**2) + 1j * (gamma * wp**2) / ((omega**2 + gamma**2) * omega)
        return np.sqrt(e_ZnO)

    # 5. Formalismo 2D Riguroso para Grafeno
    if material == "Grafeno":
        sigma = calculate_graphene_sigma(wavelength_nm)
        d_graphene = layer_info.get('d', 0.335) * 1e-9
        omega = 2 * np.pi * const.c / (wavelength_nm * 1e-9)
        eps_0 = const.epsilon_0
        eps_eff = 1.0 + (1j * sigma) / (omega * eps_0 * d_graphene)
        return np.sqrt(eps_eff)

    # 6. Constantes estándar genéricas
    if material == "Aire / Vacío":
        return 1.0 + 0j
    elif material in ["Agua (H2O)", "Agua"]:
        return 1.333 + 0j
    elif material == "BK7":
         return get_refractive_index({"material": "Vidrio (BK7)", "d": 0}, wavelength_nm)

    return 1.5 + 0j

# ==========================================
# 2. MOTOR FÍSICO (Matriz de Transferencia + Campo)
# ==========================================

def calculate_tmm(wavelength_nm, theta_deg, layers, pol='TM'):
    """
    Calcula Reflectancia y Transmitancia rigurosas.
    Implementa capas 3D estándar y formalismo 2D exacto para Grafeno.
    """
    k0 = 2 * np.pi / wavelength_nm
    theta_rad = np.radians(theta_deg)
    
    # Obtener índices y materiales
    ns = [get_refractive_index(L, wavelength_nm) for L in layers]
    ds = [L['d'] for L in layers]
    materials = [L['material'] for L in layers]
    
    # Medio de entrada (Prisma)
    n0 = ns[0]
    sin0 = np.sin(theta_rad)
    cos0 = np.lib.scimath.sqrt(1 - sin0**2)
    q0 = n0 / cos0 if pol == 'TM' else n0 * cos0
    
    M = np.identity(2, dtype=complex)
    qz_list = [cos0] # Para mantener compatibilidad con otras funciones
    
    # Iterar sobre capas intermedias
    for i in range(1, len(ns) - 1):
        if materials[i] == "Grafeno":
            # --- FORMALISMO 2D RIGUROSO PARA GRAFENO ---
            # 1. Obtener número de capas atómicas reales
            n_capas = int(layers[i].get('custom_layers', 1))
            
            # 2. Calcular conductividad de Kubo
            # Usamos el mu químico que el usuario haya definido o 0.3 eV por defecto
            mu_c = layers[i].get('custom_mu', 0.3) 
            sigma_1_capa = calculate_graphene_sigma(wavelength_nm, chemical_potential_eV=mu_c)
            sigma_total = n_capas * sigma_1_capa
            
            # 3. Normalizar conductividad con la impedancia del vacío
            Z0 = 376.730313668 # Ohms
            # En TM: la condición de contorno de Maxwell incluye proyección angular
            # J_x = sigma * E_x, y la componente H_y acopla con cos(theta).
            # En TE: E ya es puramente tangencial, no hay corrección angular.
            if pol == 'TM':
                n_prev = ns[i-1] if i > 0 else ns[0]
                cos_adj = np.lib.scimath.sqrt(1 - ((n0 / n_prev) * sin0)**2)
                sigma_norm = sigma_total * Z0 / cos_adj
            else:
                sigma_norm = sigma_total * Z0
            
            # 4. Construir Matriz de Discontinuidad Interfacial
            # En TM: H_{y,2} - H_{y,1} = J_surf = sigma * E_x
            M_layer = np.array([
                [1.0, 0.0], 
                [sigma_norm, 1.0]
            ], dtype=complex)
            
            M = np.dot(M, M_layer)
            qz_list.append(1.0) # Placeholder para grafeno (no tiene fase de propagación)
            
        else:
            # --- FORMALISMO 3D VOLUMÉTRICO (Metales y Dieléctricos) ---
            n = ns[i]
            d = ds[i]
            cos_theta = np.lib.scimath.sqrt(1 - ((n0 / n) * sin0)**2)
            q = n / cos_theta if pol == 'TM' else n * cos_theta
            
            delta = k0 * n * d * cos_theta
            
            m11 = np.cos(delta)
            m12 = (-1j / q) * np.sin(delta)
            m21 = (-1j * q) * np.sin(delta)
            m22 = np.cos(delta)
            
            M_layer = np.array([[m11, m12], [m21, m22]])
            M = np.dot(M, M_layer)
            qz_list.append(cos_theta)

    # Medio de salida (Sensor / Analito)
    nN = ns[-1]
    cosN = np.lib.scimath.sqrt(1 - ((n0 / nN) * sin0)**2)
    qz_list.append(cosN)
    qN = nN / cosN if pol == 'TM' else nN * cosN
    
    # Ecuación de coeficientes de Fresnel globales
    num = (M[0,0] + M[0,1]*qN)*q0 - (M[1,0] + M[1,1]*qN)
    den = (M[0,0] + M[0,1]*qN)*q0 + (M[1,0] + M[1,1]*qN)
    
    r = num / den
    R = np.abs(r)**2
    
    # Transmitancia
    t_coef = 2*q0 / den
    T = (np.real(qN) / np.real(q0)) * np.abs(t_coef)**2
    
    return R, T, r, t_coef, ns, ds, qz_list

def get_critical_angle(wavelength, layers):
    """
    Calcula el ángulo crítico entre el prisma (capa 0) y el medio final (capa -1).
    Theta_c = arcsin(n_fondo / n_prisma)
    """
    # Tomamos solo la parte Real del índice de refracción
    n_prisma = np.real(get_refractive_index(layers[0], wavelength))
    n_medio = np.real(get_refractive_index(layers[-1], wavelength))
    
    if n_prisma > n_medio:
        theta_rad = np.arcsin(n_medio / n_prisma)
        return np.degrees(theta_rad)
    else:
        return None # No hay ángulo crítico si el prisma es menos denso que el medio

def calculate_field_profile(wavelength_nm, theta_deg, layers, pol='TM'):
    """
    Recalcula el campo eléctrico (Ex y Ez) dentro de la estructura.
    """
    R, T, r, t, ns, ds, cos_thetas = calculate_tmm(wavelength_nm, theta_deg, layers, pol)
    
    k0 = 2 * np.pi / wavelength_nm
    theta_rad = np.radians(theta_deg)
    n0 = ns[0]
    kx = k0 * n0 * np.sin(theta_rad)
    Z0 = 376.73 # Impedancia del vacío
    
    # Puntos Z para graficar
    z_points = []
    Ex_sq = []
    Ez_sq = []
    
    # Definir amplitudes iniciales en la interfaz 0-1 (z=0)
    cos0 = np.lib.scimath.sqrt(1 - np.sin(theta_rad)**2)
    q0 = n0/cos0 if pol == 'TM' else n0*cos0
    
    current_E = 1 + r
    current_H = q0 * (1 - r)
    current_vector = np.array([[current_E], [current_H]])
    
    current_z = 0
    
    # --- CAPA 0 (Prisma/Entrada) ---
    z_pre = np.linspace(-100, 0, 50)
    kz0 = k0 * n0 * cos0
    # Campo tangencial E_x
    Ex_pre = np.exp(1j * kz0 * z_pre) + r * np.exp(-1j * kz0 * z_pre)
    # Campo magnético H_y (para Ez)
    Hy_pre = q0 * (np.exp(1j * kz0 * z_pre) - r * np.exp(-1j * kz0 * z_pre))
    
    # Ez = (kx / (omega * eps)) * Hy
    # eps = eps0 * n^2. kx/omega = n0 sin(theta)/c
    # Ez = (Z0 * n0 * sin(theta) / n^2) * Hy
    Ez_pre = (Z0 * n0 * np.sin(theta_rad) / (ns[0]**2)) * Hy_pre
    
    z_points.extend(z_pre)
    Ex_sq.extend(np.abs(Ex_pre)**2)
    Ez_sq.extend(np.abs(Ez_pre)**2)
    
    # --- CAPAS INTERNAS ---
    for i in range(1, len(layers)-1):
        if layers[i]['material'] == "Grafeno":
            # Salto en H_y, pero E_x se mantiene (2D puro)
            Z_vac = 376.73
            mu_c = layers[i].get('custom_mu', 0.3)
            n_layers = layers[i].get('custom_layers', 1)
            sigma = calculate_graphene_sigma(wavelength_nm, mu_c)
            # Misma corrección angular que en calculate_tmm para consistencia
            if pol == 'TM':
                n_prev = ns[i-1] if i > 0 else ns[0]
                cos_adj = np.lib.scimath.sqrt(1 - ((n0 / n_prev) * np.sin(theta_rad)**2))
                sigma_norm = n_layers * sigma * Z_vac / cos_adj
            else:
                sigma_norm = n_layers * sigma * Z_vac
            
            M_interface = np.array([[1.0, 0.0], [sigma_norm, 1.0]], dtype=complex)
            current_vector = np.dot(M_interface, current_vector)
            # z no cambia
        else:
            d = ds[i]
            n = ns[i]
            cos_theta = cos_thetas[i]
            kz = k0 * n * cos_theta
            q = n / cos_theta if pol == 'TM' else n * cos_theta
            
            z_internal = np.linspace(0, d, 50)
            E_start = current_vector[0,0]
            H_start = current_vector[1,0]
            
            A = 0.5 * (E_start + H_start/q)
            B = 0.5 * (E_start - H_start/q)
            
            E_layer = A * np.exp(1j * kz * z_internal) + B * np.exp(-1j * kz * z_internal)
            H_layer = q * (A * np.exp(1j * kz * z_internal) - B * np.exp(-1j * kz * z_internal))
            
            Ez_layer = (Z0 * n0 * np.sin(theta_rad) / (n**2)) * H_layer
            
            z_points.extend(current_z + z_internal)
            Ex_sq.extend(np.abs(E_layer)**2)
            Ez_sq.extend(np.abs(Ez_layer)**2)
            
            # Avanzar vector
            delta = kz * d
            M_layer = np.array([[np.cos(delta), (-1j/q)*np.sin(delta)], [(-1j*q)*np.sin(delta), np.cos(delta)]])
            current_vector = np.dot(M_layer, current_vector)
            current_z += d

    # --- CAPA N (Salida) ---
    z_post = np.linspace(0, 200, 50)
    nN = ns[-1]
    cosN = cos_thetas[-1]
    kzN = k0 * nN * cosN
    qN = nN / cosN if pol == 'TM' else nN * cosN
    
    E_interface = current_vector[0,0]
    H_interface = current_vector[1,0]
    
    # Onda transmitida
    E_post = E_interface * np.exp(1j * kzN * z_post)
    H_post = qN * E_interface * np.exp(1j * kzN * z_post)
    Ez_post = (Z0 * n0 * np.sin(theta_rad) / (nN**2)) * H_post
    
    z_points.extend(current_z + z_post)
    Ex_sq.extend(np.abs(E_post)**2)
    Ez_sq.extend(np.abs(Ez_post)**2)
    
    return np.array(z_points), np.array(Ex_sq), np.array(Ez_sq), ds


def optimize_structure(layer_indices, wl, current_layers, pol):
    """
    Optimiza el grosor de las capas continuas para minimizar la reflectancia mínima.
    """
    from scipy.optimize import differential_evolution
    
    def cost_function(d_values):
        temp_layers = [L.copy() for L in current_layers]
        for i, idx in enumerate(layer_indices):
            temp_layers[idx]['d'] = d_values[i]
        
        # Barrido angular denso para encontrar el dip de resonancia
        angles = np.linspace(30, 85, 200)
        R_vals = [calculate_tmm(wl, th, temp_layers, pol)[0] for th in angles]
        return np.min(R_vals)

    # Límites físicos para optimización continua (Metales/Dieléctricos)
    bounds = [(20.0, 90.0) for _ in layer_indices]
    
    result = differential_evolution(
        cost_function, 
        bounds, 
        seed=42, 
        maxiter=40,   # Balance entre velocidad y convergencia
        popsize=12,
        tol=1e-5
    )
    return result.x, result.fun

# ==========================================
# 3. INTERFAZ STREAMLIT
# ==========================================

st.set_page_config(page_title="Simulador de Plasmones (SPR)", layout="wide")

st.title("Simulador de Resonancia de Plasmones Superficiales (SPR)")
st.markdown("Basado en el Método de Matriz de Transferencia (TMM).")

# --- SIDEBAR: CONFIGURACIÓN GLOBAL ---
st.sidebar.header("Configuración de Luz")
wl = st.sidebar.number_input("Longitud de Onda (nm)", 300, 1500, 633)
pol = st.sidebar.selectbox("Polarización", ["TM", "TE"], index=0)
st.sidebar.info("Nota: Los plasmones de superficie (SPR) solo se excitan con polarización **TM**.")

# --- SELECCIÓN DE CAPAS ---
st.header("Configuración de la Estructura")
st.markdown("Define las capas desde el prisma (arriba) hasta el aire/medio (abajo).")

# Estado inicial de capas por defecto
if 'layers' not in st.session_state:
    st.session_state.layers = [
        {"material": "Vidrio (BK7)", "d": 0},    # Capa 0
        {"material": "Oro (Au)", "d": 45},       # Capa 1
        {"material": "Aire / Vacío", "d": 0}     # Capa 2
    ]

# Editor de capas
available_materials = [
    "Aire / Vacío", 
    "Agua (H2O)",
    "Vidrio (BK7)", 
    "Sílice (Silica)",
    "Fluoruro N-F2",
    "Zafiro Sintético (Al2O3)",
    "Vidrio Denso (SF10)",
    "Vidrio N-SF14",
    "Acrílico SUVT",
    "Dióxido de Silicio (SiO2)",
    "Cuarzo",
    "PVA",
    "Glicerina",
    "Titanio (Ti)", 
    "TiO2",
    "ZnO",
    "Oro (Au)", 
    "Plata (Ag)", 
    "Aluminio (Al)",
    "Cromo (Cr)",
    "MoS2 (Disulfuro de Molibdeno)",
    "ITO (Óxido de Indio y Estaño)",
    "Grafeno", 
    "Personalizado (Manual)"
]

# ==========================================
# SECCIÓN DE OPTIMIZACIÓN (MOVIDA AL FINAL PARA ACTUALIZACIÓN INSTANTÁNEA)
# ==========================================
st.sidebar.markdown("---")
st.sidebar.header("🤖 Diseño Inverso (IA)")

with st.sidebar.expander("Optimizar Estructura", expanded=False):
    st.write("Selecciona qué capas quieres que la IA ajuste automáticamente para lograr R=0.")
    
    # 1. Crear lista de opciones dinámicamente
    # Filtramos capa 0 y capa N (no se optimizan porque son semi-infinitas)
    opt_options = {}
    for i, L in enumerate(st.session_state.layers):
        if i > 0 and i < len(st.session_state.layers) - 1:
            label = f"Capa {i}: {L['material']} (Actual: {L['d']:.1f} nm)"
            opt_options[label] = i

    # 2. Multiselect: Permite elegir una o VARIAS
    selected_labels = st.multiselect("Capas a optimizar:", list(opt_options.keys()))
    
    # Botón de Acción
    if st.button("🚀 Optimizar Seleccionadas"):
        if not selected_labels:
            st.error("Por favor selecciona al menos una capa.")
        else:
            indices_to_opt = [opt_options[label] for label in selected_labels]
            
            with st.spinner("La IA está ajustando los parámetros (Torneo Híbrido)..."):
                
                # Identificar si hay grafeno y metales
                idx_graphene = next((idx for idx in indices_to_opt if "grafeno" in st.session_state.layers[idx]['material'].lower()), -1)
                metal_indices = [idx for idx in indices_to_opt if idx != idx_graphene]
                
                # 1. Corrección del récord global a Infinito
                best_R_global = float('inf') 
                best_config = {}
                
                # Definir capas a probar: Solo 1 capa si el usuario lo pidió, sino, de 1 a 6.
                # Para forzar que solo prumismos 27,73ebe la capa actual configurada, usamos:
                rango_capas = [st.session_state.layers[idx_graphene].get('custom_layers', 1)] if idx_graphene != -1 else [0]
                
                for n_capas in rango_capas:
                    # Fijar grafeno
                    if idx_graphene != -1:
                        st.session_state.layers[idx_graphene]['d'] = n_capas * 0.335
                        st.session_state.layers[idx_graphene]['custom_layers'] = n_capas
                    
                    # Definir función de costo basada en FWHM (Ancho a media altura)
                    def objective_smart(d_values):
                        temp_layers = [L.copy() for L in st.session_state.layers]
                        for i, m_idx in enumerate(metal_indices):
                            temp_layers[m_idx]['d'] = d_values[i] 
                            
                        # Escaneo angular con más resolución para capturar bien el ancho
                        angles_opt = np.linspace(35, 80, 400) 
                        rs = [calculate_tmm(wl, th, temp_layers, pol)[0] for th in angles_opt]
                        rs = np.array(rs)
                        
                        min_R = np.min(rs)
                        min_idx = np.argmin(rs)
                        
                        # --- CÁLCULO FÍSICO DEL FWHM ---
                        # Media altura (mitad entre el máximo posible, 1.0, y el mínimo actual)
                        half_max = (1.0 + min_R) / 2.0
                        
                        # Buscar los puntos donde cruza la media altura (Izquierda y Derecha del pozo)
                        left_side = np.where(rs[:min_idx] > half_max)[0]
                        right_side = np.where(rs[min_idx:] > half_max)[0]
                        
                        izq = left_side[-1] if len(left_side) > 0 else 0
                        der = right_side[0] + min_idx if len(right_side) > 0 else len(rs) - 1
                        
                        fwhm = angles_opt[der] - angles_opt[izq]
                        
                        # --- FUNCIÓN DE COSTO ---
                        # Alpha es el peso de la penalización (0.05 suele funcionar muy bien)
                        alpha = 0.05
                        costo_final = min_R + (alpha * fwhm)
                        
                        # Si el pozo es irrealmente ancho (falla de resonancia), penalizamos severamente
                        if fwhm > 15.0:
                            costo_final += 10.0
                            
                        return costo_final
                    
                    # 2. Límites inteligentes basados en la física del material
                    bounds = []
                    for m_idx in metal_indices:
                        nombre_mat = st.session_state.layers[m_idx]['material']
                        if "Titanio" in nombre_mat or "Cromo" in nombre_mat:
                            # Las capas de adherencia no deben pasar de 5 nm
                            bounds.append((1.0, 5.0)) 
                        else:
                            # Oro, Plata, Aluminio, etc.
                            bounds.append((20.0, 90.0))
                    
                    if metal_indices:
                        from scipy.optimize import differential_evolution
                        res = differential_evolution(objective_smart, bounds, seed=42, maxiter=50, popsize=10)
                        min_r_ronda = res.fun
                        d_metales_opt = res.x if isinstance(res.x, (list, np.ndarray)) else [res.x]
                    else:
                        min_r_ronda = objective_smart([])
                        d_metales_opt = []
                        
                    if min_r_ronda < best_R_global:
                        best_R_global = min_r_ronda
                        best_config = {
                            'n_capas_gr': n_capas,
                            'd_metales': d_metales_opt,
                            'R_min': min_r_ronda
                        }

            # --- APLICAR RESULTADOS ---
            if not best_config:
                st.error("No se pudo encontrar un mínimo físico. Revisa la configuración de capas.")
            else:
                if idx_graphene != -1:
                    st.session_state.layers[idx_graphene]['d'] = best_config['n_capas_gr'] * 0.335
                    st.session_state[f"layers_g_{idx_graphene}"] = best_config['n_capas_gr']
                    
                msg_str = ""
                for i, m_idx in enumerate(metal_indices):
                    d_final = float(best_config['d_metales'][i])
                    st.session_state.layers[m_idx]['d'] = d_final
                    st.session_state[f"d_{m_idx}"] = d_final # Actualiza el Slider
                    msg_str += f"- Capa {m_idx} ({st.session_state.layers[m_idx]['material']}): {d_final:.2f} nm\n"
                    
                st.success("¡Optimización completada con rigurosidad física!")
                st.markdown(f"**Nuevos grosores:**\n{msg_str}")
                # Le restamos la penalización para mostrar el R real si aplicó
                R_mostrar = best_config['R_min'] % 10.0 if best_config['R_min'] >= 10.0 else best_config['R_min']
                st.metric("Reflectancia Mínima Teórica", f"{R_mostrar:.6f}")
                
                st.rerun()

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Añadir/Quitar Capas")
    # Mostramos controles simples para modificar la lista
    n_capas = st.number_input("Número de Capas", min_value=2, max_value=10, value=len(st.session_state.layers))
    
    if n_capas > len(st.session_state.layers):
        for _ in range(n_capas - len(st.session_state.layers)):
            st.session_state.layers.append({"material": "Aire / Vacío", "d": 50})
    elif n_capas < len(st.session_state.layers):
        st.session_state.layers = st.session_state.layers[:n_capas]

with col2:
    st.subheader("Propiedades de Capa")
    updated_layers = []
    
    for i, layer in enumerate(st.session_state.layers):
        st.markdown(f"**Capa {i}**")
        c1, c2 = st.columns(2)
        
        # Selector de Material
        # Intentamos mantener la selección previa si existe
        current_mat_index = 0
        if layer['material'] in available_materials:
            current_mat_index = available_materials.index(layer['material'])
        
        mat = c1.selectbox(f"Material", available_materials, 
                           index=current_mat_index, key=f"mat_{i}", label_visibility="collapsed")
        
        # Lógica para Material Personalizado
        custom_n = 1.5  # Valor default
        custom_k = 0.0
        custom_layers = 1 # Para Grafeno
        custom_mu = 0.3   # Potencial químico
        if mat == "Personalizado (Manual)":
            # Mostramos inputs para n y k en una sub-columna
            c_custom1, c_custom2 = st.columns(2)
            custom_n = c_custom1.number_input(f"n (Real)", 0.0, 10.0, 1.5, step=0.0001, format="%.4f", key=f"n_custom_{i}")
            custom_k = c_custom2.number_input(f"k (Imag)", 0.0, 10.0, 0.0, step=0.0001, format="%.4f", key=f"k_custom_{i}")
        
        elif mat == "Grafeno":
            # Para Grafeno: input de número de capas atómicas (entero)
            c2_g1, c2_g2 = c2.columns(2)
            custom_layers = c2_g1.number_input(
                f"N Capas",
                min_value=0,
                max_value=20,
                value=int(layer.get('custom_layers', 1)),
                step=1,
                key=f"layers_g_{i}"
            )
            custom_mu = c2_g2.number_input(
                f"mu_c (eV)",
                min_value=0.0,
                max_value=1.5,
                value=float(layer.get('custom_mu', 0.3)),
                step=0.01,
                key=f"mu_c_{i}"
            )
            st.caption(f"⚡ Conductividad Kubo activa (Modelo 2D).")
            d_grafeno = custom_layers * 0.335
            st.caption(f"📐 Espesor bio-equivalente: **{d_grafeno:.3f} nm**")
        
        # Selector de Grosor (d) - CONDICIONAL POR MATERIAL
        if i == 0 or i == len(st.session_state.layers)-1:
            st.caption("Grosor: Semi-infinito")
            d = 0.0
        elif mat == "Grafeno":
            # El grosor ya fue calculado arriba por el input de capas
            d = d_grafeno
        else:
            # Otros materiales: input estándar en nm con 2 decimales
            key_d = f"d_{i}"
            
            if key_d not in st.session_state:
                st.session_state[key_d] = float(layer.get('d', 50.0))
            
            d = c2.number_input(
                f"Grosor (nm)", 
                min_value=0.0, 
                max_value=1000.0, 
                step=0.01,
                format="%.2f",
                key=key_d
            )
            
        # Guardamos todo en el diccionario de la capa
        updated_layers.append({
            "material": mat, 
            "d": d,
            "custom_n": custom_n, 
            "custom_k": custom_k,
            "custom_layers": custom_layers, # Guardamos N capas
            "custom_mu": custom_mu
        })
        
        st.divider() # Línea visual para separar capas
        
    st.session_state.layers = updated_layers

# --- PESTAÑAS DE RESULTADOS (VERSIÓN FINAL PRO) ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Reflectancia", "Campo", "Dispersión", "🧠 Entrenamiento IA", "⏱️ Biosensor (Sensorgrama)"])

# ==========================================
# TAB 1: GRÁFICA INTERACTIVA (PLOTLY)
# ==========================================
with tab1:
    if st.button("Calcular Curva ATR", key="btn_atr"):
        
        # 1. Cálculos con alta resolución
        angles = np.linspace(30, 85, 600) 
        R_vals = []
        
        # Barra de progreso
        prog_bar = st.progress(0)
        for i, theta in enumerate(angles):
            # Nota: calculate_tmm devuelve una tupla, tomamos el primer valor [0] que es R
            r_val = calculate_tmm(wl, theta, st.session_state.layers, pol)[0]
            R_vals.append(r_val)
            if i % 50 == 0: prog_bar.progress(i / len(angles))
        prog_bar.empty()
        
        # 2. Encontrar el mínimo (Resonancia)
        min_R = np.min(R_vals)
        min_idx = np.argmin(R_vals)
        res_angle = angles[min_idx]
        
       # ... (Cálculos previos de R_vals y min_idx igual que antes) ...
        
        # --- CÁLCULO DEL ÁNGULO CRÍTICO ---
        theta_c = get_critical_angle(wl, st.session_state.layers)
        
        # 3. Crear Gráfica Interactiva con Plotly
        fig = go.Figure()
        
        # Zona RIT (Sombreado)
        if theta_c:
            fig.add_shape(type="rect",
                x0=theta_c, y0=0, x1=85, y1=1.05,
                line=dict(width=0),
                fillcolor="rgba(200, 200, 200, 0.1)", # Gris muy suave
                layer="below"
            )
            # Línea del Ángulo Crítico
            fig.add_vline(x=theta_c, line_width=2, line_dash="dash", line_color="gray", 
                         annotation_text="Ángulo Crítico", annotation_position="top left")

        # Línea principal (Reflectancia)
        fig.add_trace(go.Scatter(
            x=angles, y=R_vals,
            mode='lines',
            name=f'Reflectancia ({pol})',
            line=dict(color='firebrick', width=3)
        ))
        
        # Marcador del Plasmón
        fig.add_trace(go.Scatter(
            x=[res_angle], y=[min_R],
            mode='markers',
            name=f'Plasmón (SPR): {res_angle:.2f}°',
            marker=dict(color='black', size=10, symbol='x')
        ))

        # ... (El resto del diseño layout sigue igual) ...
        
        # Métrica Extra
        c1, c2, c3 = st.columns(3)
        c1.metric("Ángulo Crítico (RIT)", f"{theta_c:.2f}°" if theta_c else "N/A")
        c2.metric("Ángulo de Resonancia", f"{res_angle:.2f}°")
        c3.metric("Mínimo de Reflectancia", f"{min_R:.4f}")

        st.plotly_chart(fig, use_container_width=True)
    
        with st.expander("📄 Generar Reporte Automático"):
            if min_R < 0.01:
                quality = "Excelente (Acoplamiento Crítico)"
            elif min_R < 0.1:
                quality = "Buena"
            else:
                quality = "Baja (Pobre acoplamiento)"
            
            report = f"""
            **Informe de Simulación SPR**
            
            Se analizó una estructura de {len(st.session_state.layers)} capas. 
            Para una longitud de onda de {wl} nm, se detectó el fenómeno de resonancia de plasmón superficial 
            en un ángulo de **{res_angle:.2f}°**.
        
            La eficiencia de absorción es **{quality}**, con una reflectancia mínima de {min_R:.4f}. 
            Se recomienda este sensor para aplicaciones que requieran alta sensibilidad en el rango angular de {res_angle-2:.0f}° a {res_angle+2:.0f}°.
            """
            st.markdown(report)

        # --- BOTÓN DE DESCARGA 
        df_results = pd.DataFrame({"Angulo": angles, "Reflectancia": R_vals})
        csv = df_results.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📥 Descargar Datos de la Curva (CSV)",
            data=csv,
            file_name=f"simulacion_spr_{wl}nm.csv",
            mime="text/csv",
        )

# ==========================================
# TAB 2: PERFIL DE CAMPO (MEJORADO + CORREGIDO)
# ==========================================
with tab2:
    # Usamos r"" para que Python no confunda las barras invertidas de LaTeX
    st.markdown(r"Visualiza la intensidad del campo $|E|^2$ a través de las capas.")
    
    col_input, col_plot = st.columns([1, 3])
    with col_input:
        angle_for_field = st.number_input("Ángulo de incidencia (°)", 30.0, 90.0, 43.5, step=0.1)
        st.info("Tip: Usa el ángulo donde la reflectancia es mínima.")
        
    if st.button("Generar Perfil de Campo", key="btn_field"):
        z, Ex_sq, Ez_sq, ds = calculate_field_profile(wl, angle_for_field, st.session_state.layers, pol)
        
        # Usamos Matplotlib aquí (mejor control de parches de colores)
        fig2, ax2 = plt.subplots(figsize=(8, 5))
        
        # Dibujar capas físicas (Colores de fondo)
        current_z = 0
        colors = {'Oro': '#FFD700', 'Plata': '#C0C0C0', 'Vidrio': '#E0F7FA', 'Aire': '#FFFFFF', 'Cromo': '#B0BEC5', 'Agua': '#E1F5FE'}
        
        # Capa 0
        ax2.axvspan(-100, 0, color=colors.get('Vidrio', '#E0F7FA'), alpha=0.3)
        ax2.text(-50, max(max(Ex_sq), max(Ez_sq))*0.1, "Prisma", ha='center', fontsize=8, color='gray', rotation=90)
        
        for i in range(1, len(ds)-1):
            d = ds[i]
            mat_name = st.session_state.layers[i]['material']
            c = '#F5F5F5'
            for key, val in colors.items():
                if key in mat_name: c = val
            ax2.axvspan(current_z, current_z + d, color=c, alpha=0.5)
            if d > 5:
                ax2.text(current_z + d/2, max(max(Ex_sq), max(Ez_sq))*0.9, mat_name.split()[0], ha='center', fontsize=8, rotation=90, fontweight='bold')
            current_z += d
            
        # Curvas de Campo
        ax2.plot(z, Ex_sq, color='#1565C0', linewidth=2, label=r'$|E_x|^2$ (Tangencial)')
        ax2.plot(z, Ez_sq, color='#D32F2F', linewidth=2, label=r'$|E_z|^2$ (Normal - SPP)')
        ax2.fill_between(z, Ez_sq, color='#D32F2F', alpha=0.1)
        
        ax2.set_xlabel("Posición z (nm)")
        ax2.set_ylabel(r"Intensidad de Campo Relativa")
        ax2.set_xlim(-50, current_z + 150)
        ax2.grid(True, linestyle=':', alpha=0.5)
        ax2.set_title(f"Confinamiento del Plasmón (Modo {pol} @ {angle_for_field}°)")
        ax2.legend()
        
        st.pyplot(fig2)

# ==========================================
# TAB 3: MAPA DE DISPERSIÓN (CORREGIDO)
# ==========================================
with tab3:
    st.markdown(r"### Relación de Dispersión ($\lambda$ vs $\theta$)")
    st.write("Calcula la reflectancia para múltiples longitudes de onda y ángulos a la vez.")
    
    if st.button("Generar Mapa de Calor"):
        # Definir rangos
        wls = np.linspace(400, 900, 60)  # Resolución media (60x60)
        angs = np.linspace(30, 80, 60)
        
        # Matriz vacía
        R_map = np.zeros((len(wls), len(angs)))
        
        prog = st.progress(0)
        for i, w_val in enumerate(wls):
            for j, a_val in enumerate(angs):
                # Tomamos solo la reflectancia [0] de la función
                val = calculate_tmm(w_val, a_val, st.session_state.layers, pol)[0]
                R_map[i, j] = val
            prog.progress((i+1)/len(wls))
        prog.empty()
        
        fig3, ax3 = plt.subplots(figsize=(10, 6))
        
        # imshow dibuja la matriz
        # origin='lower' pone el (0,0) abajo a la izquierda
        im = ax3.imshow(R_map, extent=[30, 80, 400, 900], 
                        origin='lower', aspect='auto', cmap='inferno', vmin=0, vmax=1)

        # ... (Código anterior del imshow y colorbar) ...
        
        # --- DIBUJAR LÍNEA DE ÁNGULO CRÍTICO (Dinámico vs Lambda) ---
        # El ángulo crítico cambia con la longitud de onda (Dispersión del vidrio)
        critical_angles = []
        for w in wls:
            ca = get_critical_angle(w, st.session_state.layers)
            critical_angles.append(ca if ca else np.nan)
            
        ax3.plot(critical_angles, wls, 'w--', linewidth=1.5, label='Línea Crítica (RIT)')
        
        # Leyenda pequeña
        ax3.legend(loc='upper right', fontsize='small', framealpha=0.2)
        
        cbar = plt.colorbar(im, ax=ax3)
        cbar.set_label("Reflectancia")
        
        ax3.set_xlabel("Ángulo de Incidencia (deg)")
        ax3.set_ylabel("Longitud de Onda (nm)")
        ax3.set_title("Mapa de Dispersión de Plasmones")
        
        # Dibujar líneas de contorno para resaltar la resonancia
        ax3.contour(angs, wls, R_map, levels=[0.1, 0.2], colors='white', linewidths=0.5, alpha=0.5)
        
        st.pyplot(fig3)

# ==========================================
# TAB 4: IA MODELO SUSTITUTO (DUAL: ÁNGULO + SENSIBILIDAD)
# ==========================================
with tab4:
    st.header("🧠 Entrenamiento de Red Neuronal Profunda")
    
    # Selector de Hardware
    use_gpu = st.checkbox("🚀 Activar aceleración por GPU (CUDA)", value=False)
    device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
    
    if use_gpu and device == "cpu":
        st.warning("Hardware CUDA no detectado. Se utilizará la CPU.")
    else:
        st.info(f"Procesando en: **{device.upper()}**")

    st.markdown(r"### 🧠 IA vs. Física: Modelo Sustituto")
    st.write("Entrena una IA para predecir la resonancia o la sensibilidad del sensor.")
    
    col_ai_config, col_ai_results = st.columns([1, 2])
    
    with col_ai_config:
        st.header("1. Configuración")
        st.info("Define con qué datos entrenar y qué caso quieres probar.")
        
        # A) MODO DE ENTRENAMIENTO
        ai_mode = st.radio(
            "¿Qué quieres predecir?",
            ["🎯 Ángulo de Resonancia (θ_SPR)", "📐 Sensibilidad (Δθ)"],
            index=0,
            key="ai_mode_selector"
        )
        is_sensitivity_mode = ("Sensibilidad" in ai_mode)
        
        # B) Parámetros de Entrenamiento
        n_samples = st.slider("Cantidad de simulaciones (Dataset)", 50, 5000, 2000)
        
        # C) Selección de Capas
        valid_indices = [i for i in range(1, len(st.session_state.layers)-1)]
        layer_names_map = {f"Capa {i}: {st.session_state.layers[i]['material']}": i for i in valid_indices}
        
        selected_labels = st.multiselect("¿Qué capas variamos?", list(layer_names_map.keys()), 
                                         default=list(layer_names_map.keys())[:1])
        
        train_indices = [layer_names_map[label] for label in selected_labels]

        # D) INPUTS DE PRUEBA
        st.markdown("---")
        st.write("**Valores de prueba (Predicción):**")
        
        user_test_values = []
        if not train_indices:
            st.warning("Selecciona al menos una capa arriba.")
        else:
            for idx in train_indices:
                mat_name = st.session_state.layers[idx]['material']
                
                val = st.number_input(f"Grosor {mat_name} (nm)", 
                                      min_value=0.0, max_value=150.0, value=45.0, 
                                      step=0.001,
                                      format="%.4f",
                                      key=f"input_test_{idx}")
                user_test_values.append(val)

        st.markdown("---")
        
        if is_sensitivity_mode:
            btn_train = st.button("🚀 Entrenar Sensibilidad (Δθ)", use_container_width=True)
        else:
            btn_train = st.button("🚀 Entrenar Predicción (θ_SPR)", use_container_width=True)

    with col_ai_results:
        st.header("2. Resultados")
        
        model = None
        scaler = None
        
        # =============================================
        # CASO A: ENTRENAR DE CERO
        # =============================================
        if btn_train and train_indices:
            spinner_msg = "Simulando cambios de índice..." if is_sensitivity_mode else "Generando datos y entrenando..."
            with st.spinner(spinner_msg):
                X = []
                y_angle = []       # Para ángulo de resonancia
                y_sensitivity = [] # Para sensibilidad
                
                temp_layers = [L.copy() for L in st.session_state.layers]
                
                prog_bar = st.progress(0)
                
                for i in range(n_samples):
                    current_grosores = []
                    
                    # Generar vector aleatorio inteligente
                    for idx_layer in train_indices:
                        if st.session_state.layers[idx_layer]['material'] == "Grafeno":
                            n_layers = np.random.randint(1, 11) 
                            val = n_layers * 0.335
                        else:
                            val = np.random.uniform(5.0, 100.0)
                        current_grosores.append(val)
                    
                    # Configurar capas con grosores aleatorios
                    for k, idx_layer in enumerate(train_indices):
                        temp_layers[idx_layer]['d'] = current_grosores[k]
                        if temp_layers[idx_layer]['material'] == "Grafeno":
                             temp_layers[idx_layer]['custom_layers'] = max(1, int(round(temp_layers[idx_layer]['d'] / 0.335)))

                    # Feature Engineering: Volumen Óptico = Σ(d_i * n_i)
                    vol_optico = 0.0
                    for k, idx_layer in enumerate(train_indices):
                        n_layer = np.real(get_refractive_index(temp_layers[idx_layer], wl))
                        vol_optico += current_grosores[k] * n_layer
                    
                    # Vector de entrada: grosores + volumen óptico
                    feature_vector = current_grosores + [vol_optico]

                    # Calcular Resonancia BASE
                    angs = np.linspace(30, 80, 100)
                    R_vals = [calculate_tmm(wl, th, temp_layers, pol)[0] for th in angs]
                    theta_base = angs[np.argmin(R_vals)]
                    
                    y_angle.append(theta_base)
                    
                    # Si estamos en modo sensibilidad, también calculamos el shift
                    if is_sensitivity_mode:
                        temp_layers_shift = [L.copy() for L in temp_layers]
                        n_last_base = get_refractive_index(temp_layers[-1], wl).real
                        temp_layers_shift[-1]['material'] = "Personalizado (Manual)"
                        temp_layers_shift[-1]['custom_n'] = n_last_base + 0.005
                        temp_layers_shift[-1]['custom_k'] = 0.0
                        
                        R_vals_shift = [calculate_tmm(wl, th, temp_layers_shift, pol)[0] for th in angs]
                        theta_shift = angs[np.argmin(R_vals_shift)]
                        y_sensitivity.append(theta_shift - theta_base)
                    
                    X.append(feature_vector)
                    if i % 10 == 0: prog_bar.progress((i+1)/n_samples)
                
                prog_bar.empty()
                
                X = np.array(X)
                
                # Escalado de datos
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)
                
                if is_sensitivity_mode:
                    y = np.array(y_sensitivity)
                else:
                    y = np.array(y_angle)
                
                # Entrenar
                X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
                model = RandomForestRegressor(n_estimators=200, max_depth=None, random_state=42)
                model.fit(X_train, y_train)
                
                st.session_state['ai_model'] = model
                st.session_state['ai_scaler'] = scaler
                st.session_state['ai_indices'] = train_indices
                st.session_state['ai_mode'] = "sensitivity" if is_sensitivity_mode else "angle"
                st.session_state['ai_test_data'] = (y_test, model.predict(X_test))
                
                if is_sensitivity_mode:
                    st.success("✅ Modelo de Sensibilidad (Δθ) Entrenado con Datos Escalados")
                else:
                    st.success("✅ Modelo de Ángulo (θ_SPR) Entrenado con Datos Escalados")

        # =============================================
        # CASO B: USAR MODELO EN MEMORIA
        # =============================================
        elif 'ai_model' in st.session_state and train_indices == st.session_state.get('ai_indices'):
            model = st.session_state['ai_model']
            scaler = st.session_state.get('ai_scaler', None)
            stored_mode = st.session_state.get('ai_mode', 'angle')
            st.info(f"Modelo en memoria: {'Sensibilidad (Δθ)' if stored_mode == 'sensitivity' else 'Ángulo (θ_SPR)'}")

        # =============================================
        # MOSTRAR RESULTADOS
        # =============================================
        if model is not None and scaler is not None:
            stored_mode = st.session_state.get('ai_mode', 'angle')
            
            # 1. Gráfica de Validación
            if 'ai_test_data' in st.session_state:
                y_test_stored, y_pred_stored = st.session_state['ai_test_data']
                r2 = r2_score(y_test_stored, y_pred_stored)
                
                col_met, col_g = st.columns([1, 2])
                col_met.metric("R² Score", f"{r2:.4f}")
                
                fig_val = plt.figure(figsize=(6, 2.5))
                
                if stored_mode == "sensitivity":
                    plt.scatter(y_test_stored, y_pred_stored, color='#00C853', alpha=0.5, s=15)
                    min_val, max_val = min(y_test_stored), max(y_test_stored)
                    plt.plot([min_val, max_val], [min_val, max_val], 'k--', lw=1)
                    plt.xlabel("Sensibilidad Real (deg)"); plt.ylabel("Predicha (deg)")
                    plt.title("Validación: Δθ (con cambio de n=0.005)")
                else:
                    plt.scatter(y_test_stored, y_pred_stored, color='#2962FF', alpha=0.5, s=15)
                    plt.plot([30, 80], [30, 80], 'r--', lw=2)
                    plt.xlabel("Ángulo Real (deg)"); plt.ylabel("Predicho (deg)")
                    plt.title("Validación: Ángulo de Resonancia (θ_SPR)")
                
                plt.grid(True, alpha=0.3)
                col_g.pyplot(fig_val)

            # 2. Predicción del Usuario
            st.divider()
            
            # Calcular Volumen Óptico para el input del usuario
            vol_optico_user = 0.0
            temp_layers_vol = [L.copy() for L in st.session_state.layers]
            for k, idx_layer in enumerate(train_indices):
                temp_layers_vol[idx_layer]['d'] = user_test_values[k]
                if temp_layers_vol[idx_layer]['material'] == "Grafeno":
                    temp_layers_vol[idx_layer]['custom_layers'] = max(1, int(round(user_test_values[k] / 0.335)))
                n_layer = np.real(get_refractive_index(temp_layers_vol[idx_layer], wl))
                vol_optico_user += user_test_values[k] * n_layer
            
            user_features = user_test_values + [vol_optico_user]
            
            # Escalar input del usuario
            input_scaled = scaler.transform([user_features])
            pred_ai = model.predict(input_scaled)[0]
            
            # Validación Física (On-the-fly)
            temp_layers_chk = [L.copy() for L in st.session_state.layers]
            for k, idx_layer in enumerate(train_indices):
                temp_layers_chk[idx_layer]['d'] = user_test_values[k]
                
            angs = np.linspace(30, 80, 200)
            Rs = [calculate_tmm(wl, th, temp_layers_chk, pol)[0] for th in angs]
            th_base_real = angs[np.argmin(Rs)]
            
            if stored_mode == "sensitivity":
                st.subheader("🔮 Predicción de Sensibilidad (Δθ)")
                
                # Calcular shift real
                temp_layers_shift_chk = [L.copy() for L in temp_layers_chk]
                n_last_base = get_refractive_index(temp_layers_chk[-1], wl).real
                temp_layers_shift_chk[-1]['material'] = "Personalizado (Manual)"
                temp_layers_shift_chk[-1]['custom_n'] = n_last_base + 0.005
                temp_layers_shift_chk[-1]['custom_k'] = 0.0
                
                Rs_shift = [calculate_tmm(wl, th, temp_layers_shift_chk, pol)[0] for th in angs]
                th_shift_real = angs[np.argmin(Rs_shift)]
                real_val = th_shift_real - th_base_real
                
                k1, k2, k3 = st.columns(3)
                k1.metric("IA: Δθ Predicho", f"{pred_ai:.4f}°")
                k2.metric("Física: Δθ Real", f"{real_val:.4f}°")
                k3.metric("Error", f"{abs(pred_ai - real_val):.4f}°")
            else:
                st.subheader("🔮 Predicción de Ángulo de Resonancia (θ_SPR)")
                
                real_val = th_base_real
                
                k1, k2, k3 = st.columns(3)
                k1.metric("IA Predice", f"{pred_ai:.2f}°")
                k2.metric("Valor Real (Física)", f"{real_val:.2f}°")
                k3.metric("Error", f"{abs(pred_ai - real_val):.3f}°")

            # 3. XAI - Importancia de Variables
            st.divider()
            if stored_mode == "sensitivity":
                st.subheader("📊 Factor de Importancia (Impacto en Sensibilidad)")
                st.caption("Al escalar los datos, vemos qué capa realmente 'mueve la aguja' del sensor.")
            else:
                st.subheader("📊 Importancia de Variables (XAI)")
                st.caption("Indica qué capa tiene más influencia en la posición del ángulo de resonancia.")
            
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
                feat_names = [f"Capa {idx}: {st.session_state.layers[idx]['material']}" for idx in train_indices] + ["Volumen Óptico"]
                
                fig_xai = plt.figure(figsize=(6, 3))
                idx_sorted = np.argsort(importances)
                bar_color = 'teal' if stored_mode == "sensitivity" else '#2962FF'
                plt.barh(range(len(idx_sorted)), importances[idx_sorted], color=bar_color)
                plt.yticks(range(len(idx_sorted)), [feat_names[i] for i in idx_sorted])
                plt.xlabel("Importancia Relativa")
                st.pyplot(fig_xai)
        else:
            st.warning("Configura y entrena para comenzar.")

        # ==========================================
# TAB 5: BIOSENSOR DINÁMICO (SENSORGRAMA) - TIPO PDF
# ==========================================
with tab5:
    st.markdown("### ⏱️ Simulación Dinámica (Sensorgrama)")
    st.write("Simula cómo cambia la señal cuando una biomolécula se adhiere a la superficie en tiempo real.")
    
    col_bio_conf, col_bio_plot = st.columns([1, 2])
    
    with col_bio_conf:
        st.info("Configuración del Evento Biológico")
        
        # Parámetros del experimento
        t_total = st.number_input("Tiempo total (segundos)", 100, 1000, 600)
        t_inject = st.number_input("Momento de inyección (s)", 50, 500, 100)
        t_wash = st.number_input("Momento de lavado (s)", 100, 900, 400)
        
        # Cambios en el índice de refracción (Delta n)
        dn_bio = st.number_input("Cambio de índice (Δn) por bacterias/proteínas", 0.0, 0.05, 0.005, format="%.4f")
        
        st.markdown("---")
        st.caption("El sistema fijará el ángulo en la pendiente de mayor sensibilidad.")
        
    with col_bio_plot:
        if st.button("▶️ Ejecutar Biosensor"):
            # 1. Encontrar el ángulo fijo de trabajo (Fixed Angle Mode)
            # Buscamos el ángulo donde la pendiente (derivada) es máxima para mayor sensibilidad
            angles_scan = np.linspace(30, 80, 500)
            R_scan = [calculate_tmm(wl, a, st.session_state.layers, pol)[0] for a in angles_scan]
            
            # Derivada numérica
            dR = np.diff(R_scan)
            # El punto de máxima pendiente suele estar un poco antes del mínimo (resonancia)
            idx_slope = np.argmax(np.abs(dR)) 
            fixed_angle = angles_scan[idx_slope]
            
            # Índice base del medio (suponemos que es la última capa, ej: Agua)
            n_base = get_refractive_index(st.session_state.layers[-1], wl).real

            # 2. Calcular sensibilidad ∂R/∂n con solo 2 llamadas a TMM (derivada numérica)
            # Válido para los pequeños Δn típicos de biosensado (Δn ~ 0.001-0.01)
            delta_n_probe = 1e-5

            layers_base = [L.copy() for L in st.session_state.layers]
            layers_base[-1]['custom_n'] = n_base
            layers_base[-1]['material'] = "Personalizado (Manual)"

            layers_pert = [L.copy() for L in st.session_state.layers]
            layers_pert[-1]['custom_n'] = n_base + delta_n_probe
            layers_pert[-1]['material'] = "Personalizado (Manual)"

            R_base_val = calculate_tmm(wl, fixed_angle, layers_base, pol)[0]
            R_pert_val = calculate_tmm(wl, fixed_angle, layers_pert, pol)[0]
            dR_dn = (R_pert_val - R_base_val) / delta_n_probe  # ∂R/∂n

            # 3. Construir perfil temporal n(t) de forma vectorizada (sin bucle)
            time = np.linspace(0, t_total, 500)  # Más puntos, sin costo extra
            current_n_array = np.full_like(time, n_base)

            # Fase 2: Asociación (Inyección)
            mask_inject = (time > t_inject) & (time <= t_wash)
            current_n_array[mask_inject] = n_base + dn_bio * (1 - np.exp(-0.02 * (time[mask_inject] - t_inject)))

            # Fase 3: Disociación (Lavado)
            mask_wash = time > t_wash
            factor_max = 1 - np.exp(-0.02 * (t_wash - t_inject))
            peak_n = n_base + dn_bio * factor_max
            current_n_array[mask_wash] = n_base + (peak_n - n_base) * np.exp(-0.01 * (time[mask_wash] - t_wash))

            # Señal de reflectancia: R(t) ≈ R_base + (∂R/∂n) · Δn(t)
            delta_n_array = current_n_array - n_base
            reflectance_signal = R_base_val + dR_dn * delta_n_array

            # 3. Graficar Sensorgrama
            fig_bio = go.Figure()
            fig_bio.add_trace(go.Scatter(x=time, y=reflectance_signal, mode='lines', name='Señal SPR', line=dict(color='purple', width=3)))
            
            # Marcar eventos
            fig_bio.add_vline(x=t_inject, line_dash="dash", annotation_text="Inyección")
            fig_bio.add_vline(x=t_wash, line_dash="dash", annotation_text="Lavado")
            
            fig_bio.update_layout(
                title=f"Sensorgrama (Monitoreo en {fixed_angle:.2f}°)",
                xaxis_title="Tiempo (s)",
                yaxis_title="Reflectancia (u.a.)",
                template="plotly_white"
            )
            st.plotly_chart(fig_bio, use_container_width=True)
            
            # Insight final
            delta_R_total = max(reflectance_signal) - min(reflectance_signal[:int(len(time)*t_inject/t_total)])
            st.success(f"🧬 Sensibilidad detectada: Cambio de {delta_R_total:.4f} en Reflectancia ante un Δn de {dn_bio}.")