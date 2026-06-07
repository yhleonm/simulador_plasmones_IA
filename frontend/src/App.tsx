import React, { useState, useEffect } from 'react';
import { 
  Box, CssBaseline, AppBar, Toolbar, Typography, Container, Paper, TextField, MenuItem, Stack, Tab, Tabs, Chip, Button
} from '@mui/material';
import axios from 'axios';
import LayerEditor from './components/LayerEditor';
import ReflectancePlot from './components/ReflectancePlot';
import FieldProfilePlot from './components/FieldProfilePlot';
import LayerSchematic from './components/LayerSchematic';
import KineticsSensorgram from './components/KineticsSensorgram';
import Reflectance2DMap from './components/Reflectance2DMap';
import XAIPanel from './components/XAIPanel';
import CurveFittingPanel from './components/CurveFittingPanel';
import type { LayerConfig } from './types';
import { getMaterials } from './api/client';
import type { MaterialInfo } from './api/client';


export default function App() {
  const [wavelength, setWavelength] = useState(633);
  const [polarization, setPolarization] = useState<'TM' | 'TE'>('TM');
  const [interrogationMode, setInterrogationMode] = useState<'angular' | 'spectral'>('angular');
  const [fixedAngle, setFixedAngle] = useState(45.0);
  const [layers, setLayers] = useState<LayerConfig[]>([
    { material: 'Vidrio (BK7)', d: 0 },
    { material: 'Oro (Au)', d: 45 },
    { material: 'Aire / Vacío', d: 0 }
  ]);
  const [tabValue, setTabValue] = useState(0);
  const [backendStatus, setBackendStatus] = useState<'online' | 'offline'>('offline');
  const [materials, setMaterials] = useState<MaterialInfo[]>([]);

  const fetchMaterials = async () => {
    try {
      const mats = await getMaterials();
      setMaterials(mats);
    } catch (err) {
      console.error("Error fetching materials list:", err);
    }
  };

  useEffect(() => {
    const checkStatus = async () => {
      try {
        let rawBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
        const rootUrl = rawBaseUrl.replace(/\/api\/?$/, '') || 'http://localhost:8000';
        await axios.get(rootUrl);
        setBackendStatus('online');
      } catch {
        setBackendStatus('offline');
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (backendStatus === 'online') {
      fetchMaterials();
    }
  }, [backendStatus]);

  const exportDesign = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({
      wavelength,
      polarization,
      interrogationMode,
      fixedAngle,
      layers
    }, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", "configuracion_sensor_spr.json");
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    document.body.removeChild(downloadAnchor);
  };

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileReader = new FileReader();
    if (e.target.files && e.target.files[0]) {
      fileReader.readAsText(e.target.files[0], "UTF-8");
      fileReader.onload = (event) => {
        try {
          const parsed = JSON.parse(event.target?.result as string);
          if (parsed.wavelength) setWavelength(parsed.wavelength);
          if (parsed.polarization) setPolarization(parsed.polarization);
          if (parsed.interrogationMode) setInterrogationMode(parsed.interrogationMode);
          if (parsed.fixedAngle) setFixedAngle(parsed.fixedAngle);
          if (parsed.layers) setLayers(parsed.layers);
        } catch (err) {
          alert("Error importando archivo JSON de configuración.");
        }
      };
    }
  };
  const printTechnicalReport = () => {
    const reportWindow = window.open("", "_blank");
    if (!reportWindow) return;

    const dateStr = new Date().toLocaleDateString('es-ES', {
      year: 'numeric', month: 'long', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });

    const layersRows = layers.map((l, i) => {
      const thickness = i === 0 || i === layers.length - 1 ? "Semi-infinito" : `${l.d} nm`;
      let extra = "-";
      if (l.material === 'Personalizado (Manual)') {
        extra = `n=${l.custom_n ?? 1.5}, k=${l.custom_k ?? 0.0}`;
      } else if (l.material === 'Grafeno') {
        extra = `${l.custom_layers ?? 1} capas, μ_c=${l.custom_mu ?? 0.3} eV`;
      }
      return `
        <tr>
          <td>Capa ${i}</td>
          <td><strong>${l.material}</strong></td>
          <td>${thickness}</td>
          <td>${extra}</td>
        </tr>
      `;
    }).join("");

    const htmlContent = `
      <html>
        <head>
          <title>Reporte Técnico - Simulador SPR</title>
          <style>
            body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; line-height: 1.6; margin: 40px; }
            h1 { color: #1565c0; border-bottom: 2px solid #1565c0; padding-bottom: 10px; margin-bottom: 5px; }
            .subtitle { font-style: italic; color: #555; margin-bottom: 30px; }
            h2 { color: #37474f; margin-top: 30px; border-bottom: 1px solid #cfd8dc; padding-bottom: 5px; }
            table { width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 25px; }
            th, td { border: 1px solid #cfd8dc; padding: 12px; text-align: left; }
            th { background-color: #f5f5f5; font-weight: bold; }
            .card { background-color: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 4px; padding: 15px; margin-bottom: 20px; }
            .flex-grid { display: flex; flex-wrap: wrap; justify-content: space-between; }
            .col { flex: 1; min-width: 200px; margin-right: 20px; }
            .col:last-child { margin-right: 0; }
            .footer-signature { margin-top: 80px; display: flex; justify-content: space-between; }
            .sig-line { border-top: 1px solid #333; width: 250px; text-align: center; padding-top: 5px; }
            @media print {
              body { margin: 20px; }
              button { display: none; }
            }
          </style>
        </head>
        <body>
          <h1>Simulador SPR - Reporte Técnico del Sensor</h1>
          <div class="subtitle">Generado el ${dateStr} - Proyecto de Tesis / Laboratorio Óptico</div>
          
          <h2>1. Configuración de Simulación Global</h2>
          <div class="card flex-grid">
            <div class="col">
              <strong>Modo de Interrogación:</strong>
              <div>${interrogationMode === 'spectral' ? 'Escaneo Espectral (λ)' : 'Escaneo Angular (θ)'}</div>
            </div>
            <div class="col">
              <strong>Polarización de Luz:</strong>
              <div>${polarization} (Transversal Magnética / Eléctrica)</div>
            </div>
            <div class="col">
              <strong>Configuración Óptica:</strong>
              <div>${interrogationMode === 'spectral' ? `Ángulo Fijo: ${fixedAngle}°` : `Longitud de Onda: ${wavelength} nm`}</div>
            </div>
          </div>

          <h2>2. Arquitectura Multicapa del Sensor</h2>
          <table>
            <thead>
              <tr>
                <th>Capa</th>
                <th>Material</th>
                <th>Espesor / Grosor</th>
                <th>Parámetros Adicionales</th>
              </tr>
            </thead>
            <tbody>
              ${layersRows}
            </tbody>
          </table>

          <h2>3. Notas y Observaciones de Diseño</h2>
          <div class="card" style="height: 120px; border: 1px dashed #999;">
            <!-- Espacio para anotaciones manuales del investigador -->
          </div>

          <div class="footer-signature">
            <div class="sig-line">Firma del Investigador</div>
            <div class="sig-line">Firma de Supervisor / Tutor</div>
          </div>

          <div style="margin-top: 40px; text-align: center;">
            <button onclick="window.print()" style="padding: 10px 20px; background-color: #1565c0; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer;">
              Imprimir / Guardar en PDF
            </button>
          </div>
        </body>
      </html>
    `;

    reportWindow.document.write(htmlContent);
    reportWindow.document.close();
  };
  return (
    <Box sx={{ display: 'flex', bgcolor: '#f5f5f5', minHeight: '100vh', flexDirection: 'column' }}>
      <CssBaseline />
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            SPR Simulator - Sistema Completo
          </Typography>
          <Chip 
            label={backendStatus === 'online' ? "CONECTADO" : "DESCONECTADO"} 
            color={backendStatus === 'online' ? "success" : "error"}
            sx={{ fontWeight: 'bold' }}
          />
        </Toolbar>
      </AppBar>
      
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Configuración Global</Typography>
          <Stack direction="row" spacing={3} sx={{ flexWrap: 'wrap', gap: 2 }}>
            <TextField
              select
              label="Modo Interrogación"
              size="small"
              sx={{ width: 220 }}
              value={interrogationMode}
              onChange={(e) => setInterrogationMode(e.target.value as 'angular' | 'spectral')}
            >
              <MenuItem value="angular">Escaneo Angular (θ)</MenuItem>
              <MenuItem value="spectral">Escaneo Espectral (λ)</MenuItem>
            </TextField>

            {interrogationMode === 'angular' ? (
              <TextField
                label="Longitud de Onda (nm)"
                type="number"
                size="small"
                value={wavelength}
                onChange={(e) => setWavelength(Number(e.target.value))}
              />
            ) : (
              <TextField
                label="Ángulo Fijo (°)"
                type="number"
                size="small"
                value={fixedAngle}
                onChange={(e) => setFixedAngle(Number(e.target.value))}
              />
            )}

            <TextField
              select
              label="Polarización"
              size="small"
              sx={{ width: 150 }}
              value={polarization}
              onChange={(e) => setPolarization(e.target.value as 'TM' | 'TE')}
            >
              <MenuItem value="TM">TM</MenuItem>
              <MenuItem value="TE">TE</MenuItem>
            </TextField>

            <Stack direction="row" spacing={2} sx={{ ml: 'auto', alignItems: 'center' }}>
              <Button variant="outlined" size="small" onClick={exportDesign}>
                Guardar JSON
              </Button>
              <Button variant="outlined" size="small" component="label">
                Cargar JSON
                <input type="file" accept=".json" hidden onChange={handleImport} />
              </Button>
              <Button variant="contained" size="small" color="primary" onClick={printTechnicalReport}>
                Imprimir Reporte
              </Button>
            </Stack>
          </Stack>
        </Paper>

        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Diseño del Sensor SPR</Typography>
          <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 3 }}>
            <Box sx={{ flex: 7.5, minWidth: 0 }}>
              <LayerEditor 
                layers={layers} 
                setLayers={setLayers} 
                wavelength={wavelength} 
                polarization={polarization} 
                materialsList={materials}
                refreshMaterials={fetchMaterials}
              />
            </Box>
            <Box sx={{ flex: 4.5, minWidth: 0 }}>
              <LayerSchematic layers={layers} />
            </Box>
          </Box>
        </Paper>

        <Paper sx={{ p: 0, overflow: 'hidden' }}>
          <Tabs 
            value={tabValue} 
            onChange={(_, v) => setTabValue(v)} 
            variant="fullWidth"
            indicatorColor="primary"
            textColor="primary"
          >
            <Tab label="Reflectancia (ATR)" />
            <Tab label="Perfil de Campo" />
            <Tab label="Sensograma (Cinética)" />
            <Tab label="Mapa de Dispersión 2D" />
            <Tab label="Análisis IA (XAI)" />
            <Tab label="Ajuste de Curvas / Solver Inverso" />
          </Tabs>
          <Box sx={{ p: 3 }}>
            {tabValue === 0 && (
              <ReflectancePlot 
                layers={layers} 
                wavelength={wavelength} 
                polarization={polarization} 
                interrogationMode={interrogationMode}
                fixedAngle={fixedAngle}
              />
            )}
            {tabValue === 1 && (
              <FieldProfilePlot 
                layers={layers} 
                wavelength={wavelength} 
                polarization={polarization} 
              />
            )}
            {tabValue === 2 && (
              <KineticsSensorgram 
                layers={layers}
                wavelength={wavelength}
                polarization={polarization}
                interrogationMode={interrogationMode}
                fixedAngle={fixedAngle}
              />
            )}
            {tabValue === 3 && (
              <Reflectance2DMap 
                layers={layers} 
                polarization={polarization} 
              />
            )}
            {tabValue === 4 && (
              <XAIPanel 
                layers={layers}
                wavelength={wavelength}
                polarization={polarization}
                interrogationMode={interrogationMode}
                fixedAngle={fixedAngle}
              />
            )}
            {tabValue === 5 && (
              <CurveFittingPanel 
                layers={layers}
                setLayers={setLayers}
                wavelength={wavelength}
                polarization={polarization}
                interrogationMode={interrogationMode}
                fixedAngle={fixedAngle}
              />
            )}
          </Box>
        </Paper>
      </Container>
    </Box>
  );
}


