import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Label, Cell
} from 'recharts';
import { 
  Box, Button, Checkbox, FormControlLabel, Paper, Typography, TextField, Stack, Divider, 
  Grid, CircularProgress, MenuItem
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import type { LayerConfig, XAIResponse, XAIVariableData, PDPPoint } from '../types';
import { simulateXAI } from '../api/client';

interface Props {
  layers: LayerConfig[];
  wavelength: number;
  polarization: 'TM' | 'TE';
  interrogationMode: 'angular' | 'spectral';
  fixedAngle: number;
}

const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300', '#00c49f', '#0088fe'];

const XAIPanel: React.FC<Props> = ({
  layers,
  wavelength,
  polarization,
  interrogationMode,
  fixedAngle
}) => {
  const [selectedIndices, setSelectedIndices] = useState<number[]>([]);
  const [minBounds, setMinBounds] = useState<{[key: number]: number}>({});
  const [maxBounds, setMaxBounds] = useState<{[key: number]: number}>({});
  
  const [loading, setLoading] = useState(false);
  const [xaiData, setXaiData] = useState<XAIResponse | null>(null);
  const [selectedSweepIndex, setSelectedSweepIndex] = useState<number>(0);

  // Initialize bounds when layers change
  useEffect(() => {
    const newMin = { ...minBounds };
    const newMax = { ...maxBounds };
    layers.forEach((l, idx) => {
      if (idx !== 0 && idx !== layers.length - 1) {
        if (newMin[idx] === undefined) {
          newMin[idx] = Math.max(5.0, Math.round(l.d * 0.5));
        }
        if (newMax[idx] === undefined) {
          newMax[idx] = Math.round(l.d * 1.5) || 100;
        }
      }
    });
    setMinBounds(newMin);
    setMaxBounds(newMax);
  }, [layers]);

  const handleToggleIndex = (idx: number) => {
    if (selectedIndices.includes(idx)) {
      setSelectedIndices(selectedIndices.filter(i => i !== idx));
    } else {
      setSelectedIndices([...selectedIndices, idx]);
    }
  };

  const handleRunXAI = async () => {
    if (selectedIndices.length === 0) {
      alert("Por favor, selecciona al menos una capa para analizar.");
      return;
    }
    
    setLoading(true);
    setXaiData(null);
    
    const bounds_min = selectedIndices.map(idx => minBounds[idx] ?? 20);
    const bounds_max = selectedIndices.map(idx => maxBounds[idx] ?? 90);
    
    try {
      const response = await simulateXAI({
        layers,
        wavelength_nm: wavelength,
        polarization,
        interrogation_mode: interrogationMode,
        fixed_angle_deg: fixedAngle,
        analyze_indices: selectedIndices,
        bounds_min,
        bounds_max
      });
      setXaiData(response);
      setSelectedSweepIndex(0);
    } catch (err) {
      console.error("XAI simulation failed:", err);
      alert("Error al ejecutar el análisis de IA.");
    } finally {
      setLoading(false);
    }
  };

  const exportXAItoCSV = () => {
    if (!xaiData) return;
    
    let metadata = "# SIMULADOR SPR-LMR - ANALISIS DE IMPORTANCIA DE VARIABLES (XAI)\n";
    metadata += `# Modo de Interrogacion: ${interrogationMode === 'spectral' ? 'Espectral' : 'Angular'}\n`;
    metadata += `# Polarizacion: ${polarization}\n`;
    metadata += `# Capas Analizadas:\n`;
    xaiData.variables.forEach((v: XAIVariableData) => {
      metadata += `#   Capa ${v.layer_index} (${v.material}): Importancia Relativa = ${(v.importance * 100).toFixed(2)}%\n`;
    });
    metadata += "# ----------------------------------------------------\n";
    
    let csvContent = metadata + "Capa,Material,Importancia Relativa\n";
    xaiData.variables.forEach((v: XAIVariableData) => {
      csvContent += `Capa ${v.layer_index},${v.material},${v.importance.toFixed(6)}\n`;
    });
    csvContent += "\n# ----------------------------------------------------\n";
    csvContent += "# BARRIDOS DE DEPENDENCIA (PDP) INDIVIDUALES\n";
    
    xaiData.variables.forEach((v: XAIVariableData) => {
      csvContent += `\n# Capa ${v.layer_index} (${v.material}) - Barrido de Espesor\n`;
      csvContent += `Espesor (nm),Resonancia (${interrogationMode === 'spectral' ? 'nm' : 'deg'})\n`;
      v.sweep.forEach((pt: PDPPoint) => {
        csvContent += `${pt.value.toFixed(2)},${pt.resonance.toFixed(6)}\n`;
      });
    });

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "analisis_ia_spr_importancias.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const intermediateLayers = layers.filter((_, idx) => idx !== 0 && idx !== layers.length - 1);
  const intermediateIndices = layers
    .map((_, idx) => idx)
    .filter(idx => idx !== 0 && idx !== layers.length - 1);

  const importanceChartData = xaiData ? xaiData.variables.map((v: XAIVariableData) => ({
    name: `Capa ${v.layer_index}`,
    importance: Number((v.importance * 100).toFixed(1))
  })) : [];

  const currentSweepVar = xaiData && xaiData.variables[selectedSweepIndex] ? xaiData.variables[selectedSweepIndex] : null;

  return (
    <Box>
      <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
        El módulo de IA Explicable (XAI) genera muestras de Monte Carlo en el backend y entrena un regresor de <strong>Random Forest</strong> 
        para clasificar el impacto relativo de los espesores sobre el mínimo de resonancia. Además, calcula los barridos de Dependencia Parcial (PDP) exactos para cada variable.
      </Typography>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 2 }}>Selección de Capas a Analizar</Typography>
            {intermediateLayers.length === 0 ? (
              <Typography variant="body2" color="textSecondary">No hay capas intermedias en el diseño actual para analizar.</Typography>
            ) : (
              <Stack spacing={2}>
                {intermediateIndices.map((layerIdx) => {
                  const layer = layers[layerIdx];
                  const isChecked = selectedIndices.includes(layerIdx);
                  return (
                    <Box key={layerIdx} sx={{ p: 1.5, border: '1px solid #e0e0e0', borderRadius: 1 }}>
                      <FormControlLabel
                        control={
                          <Checkbox 
                            checked={isChecked} 
                            onChange={() => handleToggleIndex(layerIdx)} 
                          />
                        }
                        label={<Typography variant="body2" sx={{ fontWeight: 'bold' }}>Capa {layerIdx}: {layer.material}</Typography>}
                      />
                      {isChecked && (
                        <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
                          <TextField
                            label="Mín (nm)"
                            type="number"
                            size="small"
                            value={minBounds[layerIdx] !== undefined ? minBounds[layerIdx] : 10}
                            onChange={(e) => setMinBounds({ ...minBounds, [layerIdx]: Number(e.target.value) })}
                          />
                          <TextField
                            label="Máx (nm)"
                            type="number"
                            size="small"
                            value={maxBounds[layerIdx] !== undefined ? maxBounds[layerIdx] : 100}
                            onChange={(e) => setMaxBounds({ ...maxBounds, [layerIdx]: Number(e.target.value) })}
                          />
                        </Stack>
                      )}
                    </Box>
                  );
                })}

                <Button
                  variant="contained"
                  color="secondary"
                  startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <PlayArrowIcon />}
                  onClick={handleRunXAI}
                  disabled={loading || selectedIndices.length === 0}
                  fullWidth
                  sx={{ py: 1.2, mt: 1 }}
                >
                  {loading ? 'Entrenando Regresor IA...' : 'Ejecutar Análisis IA'}
                </Button>
              </Stack>
            )}
          </Paper>
        </Grid>

        <Grid size={{ xs: 12, md: 8 }}>
          <Paper variant="outlined" sx={{ p: 2.5, display: 'flex', flexDirection: 'column', alignItems: 'center', bgcolor: '#fafafa', position: 'relative', minHeight: 350, width: '100%' }}>
            {loading && (
              <Box sx={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: 'rgba(255,255,255,0.7)', zIndex: 10 }}>
                <Stack spacing={2} sx={{ alignItems: 'center' }}>
                  <CircularProgress size={45} />
                  <Typography variant="body2" sx={{ fontWeight: 'bold', textAlign: 'center' }}>
                    Generando muestras Monte Carlo ({Math.max(200, 50 * selectedIndices.length)} puntos TMM) y entrenando Random Forest...
                  </Typography>
                </Stack>
              </Box>
            )}

            {!xaiData && !loading && (
              <Box sx={{ height: 320, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2">
                  Configura los límites y haz clic en "Ejecutar Análisis IA" para entrenar el modelo explicable.
                </Typography>
              </Box>
            )}

            {xaiData && (
              <Box sx={{ width: '100%' }}>
                <Stack direction="row" sx={{ alignItems: 'center', mb: 2 }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>Resultados de la Inteligencia Artificial</Typography>
                  <Button 
                    variant="outlined" 
                    size="small" 
                    startIcon={<DownloadIcon />} 
                    onClick={exportXAItoCSV}
                    sx={{ ml: 'auto' }}
                  >
                    Exportar CSV
                  </Button>
                </Stack>
                
                <Divider sx={{ mb: 3 }} />

                <Grid container spacing={3}>
                  <Grid size={{ xs: 12, lg: 5 }}>
                    <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary', display: 'block', mb: 2, textAlign: 'center' }}>
                      IMPORTANCIA RELATIVA DE ESPESORES (%)
                    </Typography>
                    <Paper variant="outlined" sx={{ height: 260, p: 1, bgcolor: '#fff' }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={importanceChartData} layout="vertical" margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                          <XAxis type="number" domain={[0, 100]} unit="%"/>
                          <YAxis dataKey="name" type="category" width={90} tick={{ fontSize: 10 }} />
                          <Tooltip formatter={(v) => [`${v}%`, 'Importancia']} />
                          <Bar dataKey="importance" fill="#8884d8">
                            {importanceChartData.map((_: any, index: number) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </Paper>
                  </Grid>

                  <Grid size={{ xs: 12, lg: 7 }}>
                    <Stack direction="row" sx={{ alignItems: 'center', mb: 1.5, gap: 2 }}>
                      <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary' }}>
                        BARRIDO DE DEP. PARCIAL (PDP):
                      </Typography>
                      <TextField
                        select
                        size="small"
                        value={selectedSweepIndex}
                        onChange={(e) => setSelectedSweepIndex(Number(e.target.value))}
                        sx={{ minWidth: 150, '& .MuiInputBase-input': { py: 0.5, fontSize: 11 } }}
                      >
                        {xaiData.variables.map((v: XAIVariableData, i: number) => (
                          <MenuItem key={i} value={i} sx={{ fontSize: 11 }}>Capa {v.layer_index} ({v.material})</MenuItem>
                        ))}
                      </TextField>
                    </Stack>
                    
                    {currentSweepVar && (
                      <Paper variant="outlined" sx={{ height: 260, p: 1, bgcolor: '#fff' }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={currentSweepVar.sweep} margin={{ top: 10, right: 20, left: 10, bottom: 15 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} />
                            <XAxis 
                              dataKey="value" 
                              type="number" 
                              domain={['auto', 'auto']}
                              tick={{ fontSize: 10 }}
                            >
                              <Label value="Espesor (nm)" offset={-5} position="insideBottom" style={{ fontSize: 10 }} />
                            </XAxis>
                            <YAxis 
                              domain={['auto', 'auto']}
                              tick={{ fontSize: 10 }}
                            >
                              <Label 
                                value={interrogationMode === 'spectral' ? 'λ Resonante (nm)' : 'θ Resonante (°)'} 
                                angle={-90} 
                                position="insideLeft" 
                                style={{ textAnchor: 'middle', fontSize: 10 }} 
                              />
                            </YAxis>
                            <Tooltip 
                              formatter={(val: any) => `${Number(val).toFixed(4)} ${interrogationMode === 'spectral' ? 'nm' : '°'}`}
                              labelFormatter={(label) => `Grosor: ${Number(label).toFixed(2)} nm`}
                            />
                            <Line 
                              type="monotone" 
                              dataKey="resonance" 
                              name="Posicion Resonante"
                              stroke="#ff7300" 
                              strokeWidth={3}
                              dot={false}
                              isAnimationActive={false}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      </Paper>
                    )}
                  </Grid>
                </Grid>
                
                <Box sx={{ mt: 2, p: 1.5, bgcolor: '#e3f2fd', borderRadius: 1, borderLeft: '5px solid #1976d2' }}>
                  <Typography variant="caption" sx={{ display: 'block' }}>
                    <strong>Interpretación:</strong> La variable con mayor porcentaje de importancia tiene el mayor peso en el corrimiento de la resonancia. El gráfico PDP de la derecha detalla si la relación es lineal o presenta curvatura (por ejemplo, los espesores del metal suelen exhibir picos estrechos de acoplamiento crítico).
                  </Typography>
                </Box>
              </Box>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default XAIPanel;
