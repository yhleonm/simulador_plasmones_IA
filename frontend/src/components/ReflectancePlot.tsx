import React, { useState, useEffect } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Label, Legend
} from 'recharts';
import { 
  Box, Button, CircularProgress, Typography, Paper, Divider, FormControlLabel, Checkbox, 
  TextField, Stack, Dialog, DialogTitle, DialogContent, DialogActions, Chip, ToggleButton, ToggleButtonGroup
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import QueryStatsIcon from '@mui/icons-material/QueryStats';
import { simulateReflectance } from '../api/client';
import type { LayerConfig, ReflectanceResponse } from '../types';

interface Props {
  layers: LayerConfig[];
  wavelength: number;
  polarization: 'TM' | 'TE';
  interrogationMode: 'angular' | 'spectral';
  fixedAngle: number;
}

const ReflectancePlot: React.FC<Props> = ({ layers, wavelength, polarization, interrogationMode, fixedAngle }) => {
  const [data, setData] = useState<ReflectanceResponse | null>(null);
  const [perturbedData, setPerturbedData] = useState<ReflectanceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [biosensing, setBiosensing] = useState(false);
  const [deltaN, setDeltaN] = useState(0.005);
  const [plotMode, setPlotMode] = useState<'amplitude' | 'phase'>('amplitude');
  
  // LoD state
  const isSpectral = interrogationMode === 'spectral';
  const [noise, setNoise] = useState(isSpectral ? 0.05 : 0.001);

  // Dispersion state
  const [dispersionData, setDispersionData] = useState<{ wavelength: number; thetaRes: number }[] | null>(null);
  const [loadingDispersion, setLoadingDispersion] = useState(false);
  const [openDispersion, setOpenDispersion] = useState(false);

  useEffect(() => {
    setNoise(isSpectral ? 0.05 : 0.001);
  }, [isSpectral]);

  const getBaseRefractiveIndex = (material: string, custom_n?: number) => {
    switch (material) {
      case "Aire / Vacío": return 1.0;
      case "Agua (H2O)":
      case "Agua": return 1.333;
      case "Vidrio (BK7)": return 1.515;
      case "Sílice (Silica)": return 1.457;
      case "Personalizado (Manual)": return custom_n !== undefined ? custom_n : 1.5;
      default: return 1.333;
    }
  };

  const handleSimulate = async () => {
    setLoading(true);
    try {
      // 1. Base simulation
      const baseResult = await simulateReflectance({
        wavelength_nm: wavelength,
        polarization,
        layers,
        interrogation_mode: interrogationMode,
        fixed_angle_deg: fixedAngle
      });
      setData(baseResult);
      
      // 2. Always simulate the perturbed state in the background for Sensitivity and FoM calculation
      if (layers.length > 0) {
        const perturbedLayers = [...layers];
        const lastIdx = layers.length - 1;
        const lastLayer = layers[lastIdx];
        const baseN = getBaseRefractiveIndex(lastLayer.material, lastLayer.custom_n);
        
        perturbedLayers[lastIdx] = {
          ...lastLayer,
          material: 'Personalizado (Manual)',
          custom_n: baseN + deltaN,
          custom_k: lastLayer.custom_k !== undefined ? lastLayer.custom_k : 0.0
        };

        const pertResult = await simulateReflectance({
          wavelength_nm: wavelength,
          polarization,
          layers: perturbedLayers,
          interrogation_mode: interrogationMode,
          fixed_angle_deg: fixedAngle
        });
        setPerturbedData(pertResult);
      } else {
        setPerturbedData(null);
      }
    } catch (error: any) {
      console.error("Simulation failed", error);
      alert("Error en la simulación: " + (error.message || "Error desconocido"));
    }
    setLoading(false);
  };

  const handleCalculateDispersion = async () => {
    setLoadingDispersion(true);
    const wls = [450, 500, 550, 600, 650, 700, 750, 800, 850, 900];
    const promises = wls.map(wl => simulateReflectance({
      wavelength_nm: wl,
      polarization,
      layers,
      interrogation_mode: 'angular'
    }));
    
    try {
      const results = await Promise.all(promises);
      const dataPoints = results.map((res, i) => ({
        wavelength: wls[i],
        thetaRes: res.resonance_angle || 0
      })).filter(pt => pt.thetaRes > 0);
      setDispersionData(dataPoints);
      setOpenDispersion(true);
    } catch (err) {
      console.error("Error calculating dispersion", err);
      alert("Error calculando la relación de dispersión.");
    }
    setLoadingDispersion(false);
  };

  const chartData = data ? (isSpectral ? (data.wavelengths || []) : (data.angles || [])).map((xVal, i) => ({
    xVal: xVal,
    reflectanceBase: data.reflectance[i],
    reflectancePerturbed: perturbedData ? perturbedData.reflectance[i] : null,
    phaseDiffBase: data.phase_diff ? data.phase_diff[i] : null,
    phaseDiffPerturbed: perturbedData?.phase_diff ? perturbedData.phase_diff[i] : null
  })) : [];

  // Metrics calculation
  const thetaBase = isSpectral ? data?.resonance_wavelength : data?.resonance_angle;
  const thetaPert = isSpectral ? perturbedData?.resonance_wavelength : perturbedData?.resonance_angle;
  const shift = (thetaBase !== undefined && thetaPert !== undefined) ? Math.abs(thetaPert - thetaBase) : null;
  const sensitivity = (shift !== null) ? shift / deltaN : null;
  const fwhm = data?.fwhm || 0;
  const fom = (sensitivity !== null && fwhm > 0) ? sensitivity / fwhm : null;
  const lod = (sensitivity !== null && sensitivity > 0) ? (3 * noise) / sensitivity : null;

  const exportToCSV = () => {
    if (!data) return;
    
    let metadata = "# SIMULADOR SPR-LMR - METADATOS DE REFLECTANCIA\n";
    metadata += `# Modo de Interrogacion: ${interrogationMode === 'spectral' ? 'Espectral' : 'Angular'}\n`;
    metadata += `# Polarizacion: ${polarization}\n`;
    metadata += `# Parametro Fijo: ${isSpectral ? `Angulo Fijo = ${fixedAngle}°` : `Longitud de Onda = ${wavelength} nm`}\n`;
    metadata += `# Capas del Sensor:\n`;
    layers.forEach((l, idx) => {
      const thickness = (idx === 0 || idx === layers.length - 1) ? "Semi-infinito" : `${l.d} nm`;
      let extra = "";
      if (l.material === "Personalizado (Manual)") {
        extra = ` (n=${l.custom_n ?? 1.5}, k=${l.custom_k ?? 0.0})`;
      } else if (l.material === "Grafeno") {
        extra = ` (${l.custom_layers ?? 1} capas, mu=${l.custom_mu ?? 0.3} eV)`;
      }
      metadata += `#   Capa ${idx}: ${l.material} | Espesor: ${thickness}${extra}\n`;
    });
    metadata += "# ----------------------------------------------------\n";
    
    const xHeader = isSpectral ? "Longitud de onda [nm]" : "Angulo [deg]";
    let csvContent = metadata + `${xHeader},Reflectancia Base,Fase Diff Base (rad)`;
    if (perturbedData) {
      csvContent += `,Reflectancia Perturbada (dn=${deltaN}),Fase Diff Perturbada (rad)\n`;
    } else {
      csvContent += `\n`;
    }
    
    chartData.forEach(row => {
      let line = `${row.xVal.toFixed(4)},${row.reflectanceBase.toFixed(6)},${row.phaseDiffBase?.toFixed(6) ?? ''}`;
      if (row.reflectancePerturbed !== null && row.reflectancePerturbed !== undefined) {
        line += `,${row.reflectancePerturbed.toFixed(6)},${row.phaseDiffPerturbed?.toFixed(6) ?? ''}`;
      }
      csvContent += line + `\n`;
    });
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `reflectancia_spr_${interrogationMode}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <Box>
      <Stack direction="row" spacing={3} sx={{ mb: 3, alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        <Button 
          variant="contained" 
          onClick={handleSimulate} 
          disabled={loading}
          size="large"
        >
          {loading ? <CircularProgress size={24} /> : 'Calcular Reflectancia'}
        </Button>

        <Button 
          variant="outlined" 
          color="primary"
          startIcon={loadingDispersion ? <CircularProgress size={20} /> : <QueryStatsIcon />}
          onClick={handleCalculateDispersion} 
          disabled={loadingDispersion || layers.length === 0}
        >
          Relación Dispersión
        </Button>



        <FormControlLabel
          control={
            <Checkbox 
              checked={biosensing} 
              onChange={(e) => setBiosensing(e.target.checked)} 
            />
          }
          label="Superponer Curva con Analito"
        />

        <TextField
          label="Cambio índice medio (Δn)"
          type="number"
          size="small"
          slotProps={{ htmlInput: { step: 0.001 } }}
          sx={{ width: 180 }}
          value={deltaN}
          onChange={(e) => setDeltaN(Number(e.target.value))}
        />
        <TextField
          label="Ruido instrumental (σ)"
          type="number"
          size="small"
          slotProps={{ htmlInput: { step: isSpectral ? 0.01 : 0.0001 } }}
          sx={{ width: 180 }}
          value={noise}
          onChange={(e) => setNoise(Number(e.target.value))}
        />
        
        {data && (
          <Button 
            variant="outlined" 
            startIcon={<DownloadIcon />} 
            onClick={exportToCSV}
            sx={{ ml: 'auto' }}
          >
            Exportar CSV
          </Button>
        )}
      </Stack>

      {data && (
        <Box>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, mb: 3 }}>
            <Box sx={{ minWidth: 120 }}>
              <Typography variant="caption" color="textSecondary" sx={{ display: 'block', fontWeight: 'bold' }}>
                {isSpectral ? "λ RESONANTE BASE" : "ÁNGULO RESONANTE BASE"}
              </Typography>
              <Typography variant="h6" color="primary">
                {thetaBase?.toFixed(isSpectral ? 1 : 2)}{isSpectral ? " nm" : "°"}
              </Typography>
            </Box>
            {data.sensor_mode && (
              <Box sx={{ minWidth: 120 }}>
                <Typography variant="caption" color="textSecondary" sx={{ display: 'block', fontWeight: 'bold' }}>
                  TIPO DE RESONANCIA
                </Typography>
                <Chip 
                  label={data.sensor_mode}
                  color={
                    data.sensor_mode.includes("SPR") ? "primary" : 
                    data.sensor_mode.includes("LMR") ? "secondary" : "default"
                  }
                  size="small"
                  sx={{ mt: 0.5, fontWeight: 'bold' }}
                />
              </Box>
            )}
            {thetaPert !== undefined && (
              <Box sx={{ minWidth: 120 }}>
                <Typography variant="caption" color="textSecondary" sx={{ display: 'block', fontWeight: 'bold' }}>
                  {isSpectral ? "λ CON ANALITO" : "θ CON ANALITO"}
                </Typography>
                <Typography variant="h6" color="info.main">
                  {thetaPert.toFixed(isSpectral ? 1 : 2)}{isSpectral ? " nm" : "°"}
                </Typography>
              </Box>
            )}
            {shift !== null && (
              <Box sx={{ minWidth: 120 }}>
                <Typography variant="caption" color="textSecondary" sx={{ display: 'block', fontWeight: 'bold' }}>
                  DESPLAZAMIENTO (Δ{isSpectral ? "λ" : "θ"})
                </Typography>
                <Typography variant="h6" color="warning.main">
                  {shift.toFixed(isSpectral ? 2 : 3)}{isSpectral ? " nm" : "°"}
                </Typography>
              </Box>
            )}
            <Box sx={{ minWidth: 120 }}>
              <Typography variant="caption" color="textSecondary" sx={{ display: 'block', fontWeight: 'bold' }}>
                FWHM (ANCHO DEL DIP)
              </Typography>
              <Typography variant="h6" color="secondary">
                {fwhm.toFixed(isSpectral ? 1 : 3)}{isSpectral ? " nm" : "°"}
              </Typography>
            </Box>
            {sensitivity !== null && (
              <Box sx={{ minWidth: 120 }}>
                <Typography variant="caption" color="textSecondary" sx={{ display: 'block', fontWeight: 'bold' }}>
                  SENSIBILIDAD (S)
                </Typography>
                <Typography variant="h6" sx={{ color: 'success.main', fontWeight: 'bold' }}>
                  {sensitivity.toFixed(1)} {isSpectral ? "nm/RIU" : "deg/RIU"}
                </Typography>
              </Box>
            )}
            {lod !== null && (
              <Box sx={{ minWidth: 120 }}>
                <Typography variant="caption" color="textSecondary" sx={{ display: 'block', fontWeight: 'bold' }}>
                  LÍMITE DE DETECCIÓN (LoD)
                </Typography>
                <Typography variant="h6" sx={{ color: 'success.dark', fontWeight: 'bold' }}>
                  {lod.toExponential(2)} RIU
                </Typography>
              </Box>
            )}
          </Box>

          {fom !== null && lod !== null && (
            <Box sx={{ mb: 2, p: 1.5, bgcolor: '#e8f5e9', borderRadius: 1, borderLeft: '5px solid #2e7d32' }}>
              <Typography variant="body2">
                <strong>Análisis Físico del Sensor:</strong> La Figura de Mérito es de <strong>{fom.toFixed(1)} RIU⁻¹</strong> y el Límite de Detección mínimo estimable es de <strong>{lod.toExponential(3)} RIU</strong>. Un LoD más bajo indica que el sensor puede identificar concentraciones mucho menores de moléculas orgánicas.
              </Typography>
            </Box>
          )}

          <Divider sx={{ mb: 3 }} />

          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
            <Typography variant="subtitle1" fontWeight="bold">
              {plotMode === 'amplitude' ? 'Gráfico de Reflectancia (Amplitud)' : 'Gráfico de Diferencia de Fase (Δφ = φ_TM - φ_TE)'}
            </Typography>
            <ToggleButtonGroup
              value={plotMode}
              exclusive
              onChange={(e, newMode) => { if (newMode !== null) setPlotMode(newMode); }}
              size="small"
              color="primary"
            >
              <ToggleButton value="amplitude" sx={{ textTransform: 'none', fontWeight: 'bold' }}>Amplitud (R)</ToggleButton>
              <ToggleButton value="phase" sx={{ textTransform: 'none', fontWeight: 'bold' }}>Fase / Diferencia de Fase (Δφ)</ToggleButton>
            </ToggleButtonGroup>
          </Stack>
          
          <Paper variant="outlined" sx={{ height: 420, p: 2, bgcolor: '#fff' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis 
                  dataKey="xVal" 
                  type="number" 
                  domain={isSpectral ? [400, 1000] : [30, 85]}
                  tick={{ fontSize: 12 }}
                >
                  <Label value={isSpectral ? "Longitud de Onda (nm)" : "Ángulo de Incidencia (deg)"} offset={-10} position="insideBottom" />
                </XAxis>
                <YAxis 
                  domain={plotMode === 'amplitude' ? [0, 1.05] : [-3.5, 3.5]} 
                  tick={{ fontSize: 12 }}
                  ticks={plotMode === 'amplitude' ? undefined : [-3.1416, -1.5708, 0, 1.5708, 3.1416]}
                  tickFormatter={(val) => {
                    if (plotMode === 'amplitude') return val.toFixed(1);
                    if (Math.abs(val - 3.1416) < 0.1) return 'π';
                    if (Math.abs(val - 1.5708) < 0.1) return 'π/2';
                    if (Math.abs(val) < 0.1) return '0';
                    if (Math.abs(val + 1.5708) < 0.1) return '-π/2';
                    if (Math.abs(val + 3.1416) < 0.1) return '-π';
                    return val.toFixed(2);
                  }}
                >
                  <Label 
                    value={plotMode === 'amplitude' ? "Reflectancia (R)" : "Diferencia de Fase Δφ (rad)"} 
                    angle={-90} 
                    position="insideLeft" 
                    style={{ textAnchor: 'middle' }} 
                  />
                </YAxis>
                <Tooltip 
                  formatter={(value: any) => {
                    const numVal = Number(value);
                    if (plotMode === 'amplitude') {
                      return [numVal.toFixed(4), 'Reflectancia'];
                    } else {
                      const degVal = (numVal * 180 / Math.PI).toFixed(1);
                      return [`${numVal.toFixed(4)} rad (${degVal}°)`, 'Diferencia de Fase Δφ'];
                    }
                  }}
                  labelFormatter={(label: any) => isSpectral ? `Wavelength: ${Number(label).toFixed(1)} nm` : `Ángulo: ${Number(label).toFixed(2)}°`}
                />

                <Legend verticalAlign="top" height={36} />
                
                {plotMode === 'amplitude' ? (
                  <>
                    <Line 
                      type="monotone" 
                      dataKey="reflectanceBase" 
                      name="Curva Base"
                      stroke="#d32f2f" 
                      strokeWidth={2.5} 
                      dot={false} 
                      isAnimationActive={false}
                    />
                    {perturbedData && biosensing && (
                      <Line 
                        type="monotone" 
                        dataKey="reflectancePerturbed" 
                        name={`Curva con Analito (Δn = +${deltaN})`}
                        stroke="#1976d2" 
                        strokeWidth={2.5} 
                        strokeDasharray="5 5"
                        dot={false} 
                        isAnimationActive={false}
                      />
                    )}
                  </>
                ) : (
                  <>
                    <Line 
                      type="monotone" 
                      dataKey="phaseDiffBase" 
                      name="Diferencia de Fase Base (Δφ)"
                      stroke="#9c27b0" 
                      strokeWidth={2.5} 
                      dot={false} 
                      isAnimationActive={false}
                    />
                    {perturbedData && biosensing && (
                      <Line 
                        type="monotone" 
                        dataKey="phaseDiffPerturbed" 
                        name={`Diferencia de Fase con Analito (Δn = +${deltaN})`}
                        stroke="#00bcd4" 
                        strokeWidth={2.5} 
                        strokeDasharray="5 5"
                        dot={false} 
                        isAnimationActive={false}
                      />
                    )}
                  </>
                )}

                {thetaBase && (
                  <ReferenceLine x={thetaBase} stroke={plotMode === 'amplitude' ? "#d32f2f" : "#9c27b0"} strokeDasharray="3 3">
                    <Label value={isSpectral ? "λ_Base" : "θ_Base"} position="top" fill={plotMode === 'amplitude' ? "#d32f2f" : "#9c27b0"} fontSize={10} />
                  </ReferenceLine>
                )}
                {perturbedData && biosensing && thetaPert && (
                  <ReferenceLine x={thetaPert} stroke={plotMode === 'amplitude' ? "#1976d2" : "#00bcd4"} strokeDasharray="3 3">
                    <Label 
                      value={isSpectral ? "λ_Analito" : "θ_Analito"} 
                      position="top" 
                      dy={14} 
                      fill={plotMode === 'amplitude' ? "#1976d2" : "#00bcd4"} 
                      fontSize={10} 
                    />
                  </ReferenceLine>
                )}
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Box>
      )}

      {/* Dialog for Dispersion Chart */}
      <Dialog open={openDispersion} onClose={() => setOpenDispersion(false)} maxWidth="md" fullWidth>
        <DialogTitle>Relación de Dispersión del Plasmón (θ_res vs λ)</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
            Gráfico que muestra la variación del ángulo resonante en función de la longitud de onda de excitación. 
            Ilustra la condición de acoplamiento de momento a lo largo del espectro visible e infrarrojo cercano.
          </Typography>
          {dispersionData && (
            <Paper variant="outlined" sx={{ height: 350, p: 2, bgcolor: '#fff' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dispersionData} margin={{ top: 10, right: 30, left: 20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis 
                    dataKey="wavelength" 
                    type="number" 
                    domain={[400, 950]}
                    tick={{ fontSize: 12 }}
                  >
                    <Label value="Longitud de Onda (nm)" offset={-10} position="insideBottom" />
                  </XAxis>
                  <YAxis 
                    domain={['auto', 'auto']}
                    tick={{ fontSize: 12 }}
                  >
                    <Label value="Ángulo Resonante θ_SPR (°)" angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} />
                  </YAxis>
                  <Tooltip 
                    formatter={(value: any) => `${Number(value).toFixed(2)}°`}
                    labelFormatter={(label: any) => `λ: ${label} nm`}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="thetaRes" 
                    name="Ángulo de Resonancia"
                    stroke="#1565c0" 
                    strokeWidth={2.5} 
                    dot={true} 
                  />
                </LineChart>
              </ResponsiveContainer>
            </Paper>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDispersion(false)}>Cerrar</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ReflectancePlot;



