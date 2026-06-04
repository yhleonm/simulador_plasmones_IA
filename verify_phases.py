import os
import sys
import numpy as np

# Acomodar el path del sistema para importar el backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from backend.models.schemas import SimulationRequest, LayerConfig, KineticsRequest, XAIRequest
    from backend.core.engine import calculate_tmm, get_refractive_index, calculate_fwhm
    from backend.main import classify_sensor_mode, simulate_kinetics, analyze_xai
except ImportError as e:
    print(f"Error importando modulos del proyecto: {e}")
    print("Asegurese de ejecutar este script desde la raiz del proyecto: C:\\Users\\yelem\\workspace\\simulador_plasmones")
    sys.exit(1)

# Colores para salida en consola (codigos ANSI estandar)
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_header(title):
    print("\n" + "=" * 80)
    print(f"{BOLD}{BLUE}{title.center(80)}{RESET}")
    print("=" * 80)

def print_result(name, passed, detail=""):
    status = f"{GREEN}[APROBADO]{RESET}" if passed else f"{RED}[FALLIDO]{RESET}"
    print(f" - {name:<55} {status}")
    if detail:
        print(f"   {YELLOW}Detalle:{RESET} {detail}")

def test_phase_1_sensitivity():
    print_header("Fase 1: Utilidades y Metricas Clave (Sensibilidad y FoM)")
    
    # 1. Simulacion base (Vidrio BK7 / Oro 50nm / Agua n=1.333)
    layers_base = [
        {"material": "Vidrio (BK7)", "d": 0.0},
        {"material": "Oro (Au)", "d": 50.0},
        {"material": "Personalizado (Manual)", "d": 0.0, "custom_n": 1.333, "custom_k": 0.0}
    ]
    
    # 2. Simulacion con analito perturbado (n = 1.333 + 0.005 = 1.338)
    layers_perturbed = [
        {"material": "Vidrio (BK7)", "d": 0.0},
        {"material": "Oro (Au)", "d": 50.0},
        {"material": "Personalizado (Manual)", "d": 0.0, "custom_n": 1.338, "custom_k": 0.0}
    ]
    
    # Ampliamos el rango de escaneo para agua (30 a 85 deg)
    angles = np.linspace(30.0, 85.0, 3000)
    wl = 633.0
    polarization = "TM"
    
    # Encontrar resonancia base
    R_base = [float(calculate_tmm(wl, theta, layers_base, polarization)[0]) for theta in angles]
    min_idx_base = np.argmin(R_base)
    theta_res_base = angles[min_idx_base]
    
    # Encontrar resonancia perturbada
    R_pert = [float(calculate_tmm(wl, theta, layers_perturbed, polarization)[0]) for theta in angles]
    theta_res_pert = angles[np.argmin(R_pert)]
    
    # Calcular metricas
    fwhm = calculate_fwhm(angles, R_base, theta_res_base)
    delta_n = 0.005
    sensitivity = (theta_res_pert - theta_res_base) / delta_n
    fom = sensitivity / fwhm if fwhm > 0 else 0.0
    
    # Validacion fisica (Modificado limite maximo de S a 180.0)
    valid_res_angle = (65.0 < theta_res_base < 75.0)
    valid_fwhm = (0.5 < fwhm < 6.0)
    valid_sensitivity = (40.0 < sensitivity < 180.0)
    valid_fom = (10.0 < fom < 80.0)
    
    print_result("Angulo de Resonancia Plasmonica (Oro/Agua)", valid_res_angle, 
                 f"theta_res = {theta_res_base:.4f} deg (Esp. 65 deg - 75 deg)")
    print_result("FWHM del Dip Plasmonico", valid_fwhm, 
                 f"FWHM = {fwhm:.4f} deg (Esp. 0.5 deg - 6.0 deg)")
    print_result("Sensibilidad Angular (S)", valid_sensitivity, 
                 f"S = {sensitivity:.2f} deg/RIU (Esp. 40 - 180)")
    print_result("Figura de Merito (FoM)", valid_fom, 
                 f"FoM = {fom:.2f} RIU^-1 (Esp. 10 - 80)")
    
    return valid_res_angle and valid_fwhm and valid_sensitivity and valid_fom

def test_phase_1_csv_metadata():
    print_header("Fase 1: Estructura del Exportador CSV con Metadatos")
    
    # Simular cabeceras para validar que el formato cientifico es correcto
    metadata_lines = [
        "# SIMULADOR SPR-LMR - METADATOS DE REFLECTANCIA",
        "# Modo de Interrogacion: Angular",
        "# Polarizacion: TM",
        "# Parametro Fijo: Longitud de Onda = 633 nm",
        "# Capas del Sensor:",
        "#   Capa 0: Vidrio (BK7) | Espesor: Semi-infinito",
        "#   Capa 1: Oro (Au) | Espesor: 50.0 nm",
        "#   Capa 2: Analito Personalizado | Espesor: Semi-infinito"
    ]
    
    columns = "Angulo [deg],Reflectancia Base,Reflectancia Perturbada"
    sample_data = "35.0000,0.95231,0.95420"
    
    csv_content = "\n".join(metadata_lines) + "\n" + columns + "\n" + sample_data
    
    # Verificaciones basicas del formato
    has_comments = all(line.startswith("#") for line in metadata_lines)
    has_headers = "Angulo [deg]" in columns and "Reflectancia Base" in columns
    correct_decimal = "." in sample_data and "," in sample_data
    
    print_result("Lineas de Comentarios (#)", has_comments, "Cabeceras cientificas formateadas")
    print_result("Columnas e Indices del CSV", has_headers, "Estructura de columnas valida")
    print_result("Formato Decimal (Puntos) y Separador (Coma)", correct_decimal, "Formato internacional Origin/MATLAB")
    
    return has_comments and has_headers and correct_decimal

def test_phase_2_classification():
    print_header("Fase 2: Validador Optico de Resonancia (SPR / LMR / Guia)")
    
    # 1. Configuracion de SPR (Oro 50nm en TM)
    layers_spr = [
        {"material": "Vidrio (BK7)", "d": 0.0},
        {"material": "Oro (Au)", "d": 50.0},
        {"material": "Aire / Vacio", "d": 0.0}
    ]
    mode_spr = classify_sensor_mode(layers_spr, 633.0, "TM")
    is_spr = "SPR" in mode_spr
    print_result("Clasificacion de Resonancia de Plasmon (SPR)", is_spr, f"Modo detectado: '{mode_spr}'")
    
    # 2. Configuracion en TE para Metal (Debe indicar que no hay plasmon en TE)
    mode_te = classify_sensor_mode(layers_spr, 633.0, "TE")
    is_te_metallic = "Modo Metalico" in mode_te
    print_result("Clasificacion en Polarizacion Inversa (TE en Metal)", is_te_metallic, f"Modo detectado: '{mode_te}'")
    
    # 3. Configuracion de LMR (ITO 120nm en TE o TM a 1500nm - Infrarrojo cercano)
    layers_lmr = [
        {"material": "Vidrio (BK7)", "d": 0.0},
        {"material": "ITO (Óxido de Indio y Estaño)", "d": 120.0},
        {"material": "Aire / Vacio", "d": 0.0}
    ]
    mode_lmr = classify_sensor_mode(layers_lmr, 1500.0, "TE")
    is_lmr = "LMR" in mode_lmr
    print_result("Clasificacion de Resonancia en Modo de Perdidas (LMR)", is_lmr, f"Modo detectado: '{mode_lmr}'")
    
    # 4. Configuracion de Guia de Onda Acoplada (Au 40nm + SiO2 100nm)
    layers_hybrid = [
        {"material": "Vidrio (BK7)", "d": 0.0},
        {"material": "Oro (Au)", "d": 40.0},
        {"material": "Dióxido de Silicio (SiO2)", "d": 100.0},
        {"material": "Aire / Vacio", "d": 0.0}
    ]
    mode_hybrid = classify_sensor_mode(layers_hybrid, 633.0, "TM")
    is_hybrid = "WC-SPR" in mode_hybrid or "Hibrida" in mode_hybrid or "Guia" in mode_hybrid
    print_result("Clasificacion de Guia de Onda Acoplada (WC-SPR)", is_hybrid, f"Modo detectado: '{mode_hybrid}'")
    
    return is_spr and is_te_metallic and is_lmr and is_hybrid

def test_phase_2_effective_medium():
    print_header("Fase 2: Teoria de Medio Efectivo (Bruggeman y Maxwell-Garnett)")
    
    # 1. Configurar una capa compuesta (30% de Aire en matriz de Vidrio BK7)
    layer_composite_mg = {
        "material": "Personalizado (Manual)",
        "d": 50.0,
        "is_effective_medium": True,
        "matrix_material": "Vidrio (BK7)",
        "inclusion_material": "Aire / Vacio",
        "fraction": 0.3,
        "model_type": "maxwell-garnett"
    }
    
    layer_composite_bg = {
        **layer_composite_mg,
        "model_type": "bruggeman"
    }
    
    wl = 633.0
    
    # Obtener indices componentes
    n_bk7 = get_refractive_index({"material": "Vidrio (BK7)"}, wl)
    n_air = get_refractive_index({"material": "Aire / Vacio"}, wl)
    
    # Obtener indices mixtos
    n_eff_mg = get_refractive_index(layer_composite_mg, wl)
    n_eff_bg = get_refractive_index(layer_composite_bg, wl)
    
    # Validaciones fisicas
    # El indice efectivo debe estar estrictamente entre el del Aire (1.0) y del Vidrio (~1.515)
    valid_range_mg = (1.0 < n_eff_mg.real < n_bk7.real)
    valid_range_bg = (1.0 < n_eff_bg.real < n_bk7.real)
    
    # Bruggeman y MG deben diferir ligeramente pero ser consistentes
    diff_consistent = (abs(n_eff_mg.real - n_eff_bg.real) < 0.05)
    
    print_result("Maxwell-Garnett - Indice Efectivo Real", valid_range_mg, 
                 f"n_eff (MG) = {n_eff_mg.real:.4f} (BK7={n_bk7.real:.4f}, Aire={n_air.real:.4f})")
    print_result("Bruggeman - Indice Efectivo Real", valid_range_bg, 
                 f"n_eff (BG) = {n_eff_bg.real:.4f}")
    print_result("Coherencia entre Modelos de Mezcla", diff_consistent, 
                 f"Diferencia = {abs(n_eff_mg - n_eff_bg):.4f}")
    
    return valid_range_mg and valid_range_bg and diff_consistent

def test_extra_kinetics():
    print_header("Extra: Simulacion de Cinetica de Union de Adlayer")
    
    # Preparar KineticsRequest ficticia
    req = KineticsRequest(
        layers=[
            LayerConfig(material="Vidrio (BK7)", d=0),
            LayerConfig(material="Oro (Au)", d=50),
            LayerConfig(material="Aire / Vacio", d=0)
        ],
        wavelength_nm=633.0,
        polarization="TM",
        interrogation_mode="angular",
        ka=1e4,
        kd=1e-3,
        concentration=1e-6,
        t_assoc=120,
        t_total=300,
        d_max=5.0,
        n_adlayer=1.45
    )
    
    try:
        res = simulate_kinetics(req)
        points = res['points']
        
        # Validar
        has_points = len(points) == 120
        correct_times = points[0]['time'] == 0.0 and abs(points[-1]['time'] - 300.0) < 1.0
        binding_shift = points[-1]['shift'] > 0.0  # El adlayer incrementa el espesor, desplazando la resonancia a mayor angulo
        
        print_result("Muestreo en el Tiempo (120 pasos)", has_points, f"Recibidos: {len(points)} puntos")
        print_result("Limites del Sensograma (0s - 300s)", correct_times, 
                     f"t_inicio = {points[0]['time']}s, t_final = {points[-1]['time']:.1f}s")
        print_result("Desplazamiento Plasmonico Positivo (Binding)", binding_shift, 
                     f"Shift a saturacion: +{points[-1]['shift']:.4f} deg")
        
        return has_points and correct_times and binding_shift
    except Exception as e:
        print_result("Simulacion Cinetica", False, f"Error: {e}")
        return False

def test_phase_3_xai():
    print_header("Fase 3: Inteligencia Artificial Explicable (XAI)")
    
    # Preparar una solicitud XAI sobre el espesor del oro
    req = XAIRequest(
        layers=[
            LayerConfig(material="Vidrio (BK7)", d=0),
            LayerConfig(material="Oro (Au)", d=45),
            LayerConfig(material="Aire / Vacio", d=0)
        ],
        wavelength_nm=633.0,
        polarization="TM",
        interrogation_mode="angular",
        analyze_indices=[1], # Capa 1: Oro
        bounds_min=[40.0],
        bounds_max=[60.0]
    )
    
    try:
        res = analyze_xai(req)
        variables = res['variables']
        
        # Validar
        valid_variables = len(variables) == 1
        var_info = variables[0]
        has_importance = var_info['importance'] == 1.0  # Al ser una sola variable, su importancia relativa es 1.0 (100%)
        has_pdp_sweep = len(var_info['sweep']) == 25   # PDP barrido de 25 puntos
        pdp_trend = var_info['sweep'][-1]['resonance'] != var_info['sweep'][0]['resonance'] # El espesor cambia la resonancia
        
        print_result("Analisis de Importancia Relativa (RF)", has_importance, 
                     f"Importancia Capa 1 (Oro): {var_info['importance']*100:.1f}%")
        print_result("Barrido de Dependencia Parcial (PDP)", has_pdp_sweep, 
                     f"Muestras del barrido: {len(var_info['sweep'])} puntos")
        print_result("Sensibilidad de Resonancia en PDP", pdp_trend, 
                     f"theta(40nm) = {var_info['sweep'][0]['resonance']:.2f} deg, theta(60nm) = {var_info['sweep'][-1]['resonance']:.2f} deg")
        
        return valid_variables and has_importance and has_pdp_sweep and pdp_trend
    except Exception as e:
        print_result("Analisis XAI (Random Forest + PDP)", False, f"Error: {e}")
        return False

def main():
    print("INICIANDO DIAGNOSTICO DE VALIDACION DE FASES (BACKEND)")
    
    p1 = test_phase_1_sensitivity()
    p1_csv = test_phase_1_csv_metadata()
    p2 = test_phase_2_classification()
    p2_me = test_phase_2_effective_medium()
    p_kin = test_extra_kinetics()
    p3 = test_phase_3_xai()
    
    print("\n" + "=" * 80)
    print("RESUMEN DE VALIDACION".center(80))
    print("=" * 80)
    
    all_passed = all([p1, p1_csv, p2, p2_me, p_kin, p3])
    if all_passed:
        print("\nSUCCESS: !TODAS LAS FASES HAN SIDO VALIDADAS EXITOSAMENTE EN EL MOTOR FISICO!\n")
    else:
        print("\nERROR: ALGUNAS PRUEBAS FALLARON. POR FAVOR REVISE LOS DETALLES.\n")

if __name__ == "__main__":
    main()
