# Simulador SPR - Arquitectura (FastAPI + React)

Esta es la versión oficial del simulador de plasmones, diseñada para ser rápida, escalable e interactiva.

## 🚀 Cómo ejecutar

### 1. Backend (FastAPI)
Desde la raíz del proyecto:

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
python -m backend.main
```
El backend estará disponible en `http://localhost:8000`. Puedes ver la documentación interactiva en `http://localhost:8000/docs`.

### 2. Frontend (React + Vite)
Desde la carpeta `frontend/`:

```bash
# Instalar dependencias
npm install

# Ejecutar cliente de desarrollo
npm run dev
```
El frontend estará disponible en `http://localhost:5173`.

## 🛠️ Tecnologías
- **Backend**: FastAPI, NumPy, SciPy (TMM Engine).
- **Frontend**: React (TypeScript), Vite, Material UI, Plotly.js.
