import os
import pandas as pd
import warnings
warnings.filterwarnings('ignore') # Ocultar advertencias de pandas

def limpiar_csvs_refractive_index():
    carpeta = './database' # Busca en la carpeta actual
    archivos_csv = [f for f in os.listdir(carpeta) if f.endswith('.csv')]
    
    if not archivos_csv:
        print("❌ No se encontraron archivos .csv en esta carpeta.")
        return

    for filename in archivos_csv:
        filepath = os.path.join(carpeta, filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            lineas = f.read().split('\n')
        
        n_wls, n_vals = [], []
        k_wls, k_vals = [], []
        
        modo_actual = 'n' # Por defecto asumimos que el primer bloque es 'n'
        
        for linea in lineas:
            linea = linea.strip().lower()
            if not linea: continue
            
            # Detectar cambio de bloque
            if 'wl' in linea and 'k' in linea:
                modo_actual = 'k'
                continue
            if 'wl' in linea and 'n' in linea:
                modo_actual = 'n'
                continue
                
            # Extraer números
            try:
                partes = linea.split(',')
                wl = float(partes[0])
                val = float(partes[1])
                
                if modo_actual == 'n':
                    n_wls.append(wl)
                    n_vals.append(val)
                elif modo_actual == 'k':
                    k_wls.append(wl)
                    k_vals.append(val)
            except ValueError:
                pass # Ignorar líneas que no son números (como encabezados extra)

        # Crear DataFrames
        import pandas as pd # Aseguramos pandas
        df_n = pd.DataFrame({'wl': n_wls, 'n': n_vals}) if n_wls else pd.DataFrame()
        df_k = pd.DataFrame({'wl': k_wls, 'k': k_vals}) if k_wls else pd.DataFrame()
        
        # Fusionar inteligentemente
        if not df_n.empty and not df_k.empty:
            # Unimos todas las longitudes de onda y ordenamos
            df_final = pd.merge(df_n, df_k, on='wl', how='outer').sort_values('wl').reset_index(drop=True)
            # Interpolamos los vacíos donde no coincidían las longitudes de onda
            df_final['n'] = df_final['n'].interpolate(method='linear').bfill().ffill()
            df_final['k'] = df_final['k'].interpolate(method='linear').bfill().ffill()
        elif not df_n.empty:
            df_final = df_n.copy()
            df_final['k'] = 0.0 # Si no hay k, es un material transparente
        else:
            print(f"⚠️ No se encontraron datos válidos en {filename}")
            continue

        # Sobreescribir el archivo original con la tabla limpia de 3 columnas
        df_final.to_csv(filepath, index=False)
        print(f"✅ ¡Archivo limpiado y alineado!: {filename}")

if __name__ == "__main__":
    print("Iniciando limpieza de base de datos...")
    limpiar_csvs_refractive_index()
    print("¡Proceso completado! Tus datos están listos para la simulación.")
