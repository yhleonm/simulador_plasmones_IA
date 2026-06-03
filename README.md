# Simulador de Resonancia de Plasmones Superficiales (SPR)

Este proyecto es una aplicación web interactiva desarrollada con **Streamlit** para simular y optimizar sensores de Resonancia de Plasmones Superficiales (SPR) utilizando el **Método de Matriz de Transferencia (TMM)**.

## 🚀 Características

- **Simulación TMM**: Cálculo preciso de reflectancia y transmitancia para estructuras multicapa.
- **Perfil de Campo**: Visualización de la intensidad del campo eléctrico ($|E|^2$) a través de las interfaces.
- **Optimización con IA**: Uso de algoritmos de optimización global (como Evolución Diferencial) para encontrar el acoplamiento crítico (R ≈ 0).
- **Integración de Grafeno**: Modelado de la conductividad óptica del grafeno mediante la formalismo de Kubo.
- **Base de Datos de Materiales**: Carga de índices de refracción desde archivos CSV (Johnson & Christy).

## 📁 Estructura del Proyecto

- `app.py`: Aplicación principal de Streamlit.
- `database/`: Contiene archivos CSV con constantes ópticas de materiales (n, k).
  - `Au_Johnson.csv`: Datos para Oro.
  - `Ag_Johnson.csv`: Datos para Plata.
- `requirements.txt`: Lista de dependencias de Python.
- `calc_sensitivity.py`: Script para calcular la sensibilidad del sensor.
- `plot_feature_importance.py`: Análisis XAI para entender el impacto de cada parámetro.
- `verify_graphene.py`: Verificación del modelo de grafeno.

## 🛠️ Instalación

Para ejecutar el simulador localmente:

1. Instala las dependencias:

   ```bash
   pip install -r requirements.txt
   ```

2. Ejecuta la aplicación:

   ```bash
   streamlit run app.py
   ```

## 🎓 Contexto Académico (Tesis)

Este simulador permite el diseño asistido por computadora de biosensores basados en SPR, explorando configuraciones de Kretschmann y Otto. Se pone especial énfasis en el uso de materiales 2D como el grafeno para mejorar la sensibilidad y la estabilidad del sensor.
