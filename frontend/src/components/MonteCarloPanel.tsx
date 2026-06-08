import React, { useState } from 'react';
import {
  Box, Button, CircularProgress, Typography, Paper, Stack, Grid,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  TextField, Slider, Card, CardContent, Checkbox
} from '@mui/material';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine, Label,
  BarChart, Bar
} from 'recharts';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AnalyticsIcon from '@mui/icons-material/Analytics';

import { simulateMonteCarlo } from '../api/client';
import type { LayerConfig, MonteCarloResponse } from '../types';

interface Props {
  layers: LayerConfig[];
  wavelength: number;
  polarization: 'TM' | 'TE';
  interrogationMode: 'angular' | 'spectral';
  fixedAngle: number;
  temperature_c?: number;
}

interface PerturbationRow {
  layerIndex: number;
  material: string;
  nominal_d: number;
  nominal_n_desc: string;
  std_d: string;
  std_n: string;
  std_k: string;
  enabled_d: boolean;
  enabled_n: boolean;
  enabled_k: boolean;
}

const MonteCarloPanel: React.FC<Props> = ({
  layers, wavelength, polarization, interrogationMode, fixedAngle, temperature_c = 20.0
}) => {
  const [runs, setRuns] = useState<number>(100);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MonteCarloResponse | null>(null);

  // Initialize perturbations for each layer
  const [perturbations, setPerturbations] = useState<PerturbationRow[]>(() => 
    layers.map((l, i) => {
      let nominal_n_desc = "Variable";
      if (l.material === "Personalizado (Manual)") {
        nominal_n_desc = `${l.custom_n ?? 1.5} + ${l.custom_k ?? 0.0}i`;
      } else if (l.material === "Aire / Vacío") {
        nominal_n_desc = "1.0";
      } else if (l.material === "Agua (H2O)" || l.material === "Agua") {
        nominal_n_desc = "1.333";
      } else if (l.material === "Vidrio (BK7)") {
        nominal_n_desc = "1.515";
      }
      
      const isBoundary = (i === 0 || i === layers.length - 1);
      
      return {
        layerIndex: i,
        material: l.material,
        nominal_d: l.d,
        nominal_n_desc,
        std_d: isBoundary ? "0.0" : "1.0", 
        std_n: isBoundary ? "0.0" : "0.002", 
        std_k: isBoundary ? "0.0" : "0.001",
        enabled_d: !isBoundary,
        enabled_n: false,
        enabled_k: false
      };
    })
  );

  const handlePerturbationChange = (idx: number, field: keyof PerturbationRow, value: any) => {
    setPerturbations(prev => prev.map((p, i) => i === idx ? { ...p, [field]: value } : p));
  };

  const handleRunMonteCarlo = async () => {
    setLoading(true);
    setResult(null);
    try {
      const activePerturbs = perturbations
        .filter(p => p.enabled_d || p.enabled_n || p.enabled_k)
        .map(p => ({
          layer_index: p.layerIndex,
          std_d: p.enabled_d ? parseFloat(p.std_d) || 0.0 : 0.0,
          std_n: p.enabled_n ? parseFloat(p.std_n) || 0.0 : 0.0,
          std_k: p.enabled_k ? parseFloat(p.std_k) || 0.0 : 0.0,
        }))
        .filter(p => p.std_d > 0 || p.std_n > 0 || p.std_k > 0);

      const res = await simulateMonteCarlo({
        wavelength_nm: wavelength,
        polarization,
        layers,
        interrogation_mode: interrogationMode,
        fixed_angle_deg: fixedAngle,
        temperature_c,
        runs,
        perturbations: activePerturbs
      });
      setResult(res);
    } catch (error: any) {
      console.error(error);
      alert("Error en Monte Carlo: " + (error.response?.data?.detail || error.message || "Error desconocido"));
    }
    setLoading(false);
  };

  const isSpectral = interrogationMode === 'spectral';
  const unit = isSpectral ? 'nm' : 'deg';

  // Construct chart data for the curves plot (nominal + p5 + p95 + Spaghetti samples)
  const curvesChartData = result ? result.x_grid.map((xVal, i) => {
    const row: any = {
      xVal,
      nominal: result.nominal_curve[i],
      p5: result.p5_curve[i],
      p95: result.p95_curve[i]
    };
    result.sample_curves.forEach((curve, cIdx) => {
      row[`sample_${cIdx}`] = curve[i];
    });
    return row;
  }) : [];

  // Construct histogram data
  const histogramData: { binCenter: number; Frecuencia: number }[] = result && result.resonance_values.length > 0 ? (() => {
    const vals = result.resonance_values;
    const numBins = 15;
    const minVal = Math.min(...vals);
    const maxVal = Math.max(...vals);
    const range = maxVal - minVal;
    
    if (range === 0) {
      return [{ binCenter: parseFloat(minVal.toFixed(2)), Frecuencia: vals.length }];
    }
    
    const binWidth = range / numBins;
    const bins = Array.from({ length: numBins }, (_, idx) => {
      const bMin = minVal + idx * binWidth;
      const bMax = bMin + binWidth;
      const count = vals.filter(v => v >= bMin && (idx === numBins - 1 ? v <= bMax : v < bMax)).length;
      return {
        binCenter: parseFloat((bMin + binWidth / 2).toFixed(isSpectral ? 1 : 3)),
        Frecuencia: count
      };
    });
    return bins;
  })() : [];

  return (
    <Box>
      <Paper variant="outlined" sx={{ p: 3, mb: 4, bgcolor: '#fafafa' }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 2 }}>
          <AnalyticsIcon color="primary" />
          <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
            Análisis de Tolerancia y Robustez Monte Carlo
          </Typography>
        </Stack>
        <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
          Esta herramienta simula la variabilidad física debida a tolerancias de fabricación o incertidumbre de medición. 
          Introduce perturbaciones gaussianas independientes en el grosor o índice de refracción de las capas seleccionadas y evalúa 
          estadísticamente la estabilidad del acoplamiento resonante.
        </Typography>

        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, md: 8 }}>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead sx={{ bgcolor: '#f0f4f8' }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 'bold' }}>Capa</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>Material</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }} align="right">Espesor Nominal</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>σ Espesor (nm)</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>σ Índice n</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>σ Extinción k</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {perturbations.map((p, idx) => {
                    const isBoundary = (idx === 0 || idx === layers.length - 1);
                    return (
                      <TableRow key={idx} hover>
                        <TableCell sx={{ fontWeight: 'bold' }}>{idx}</TableCell>
                        <TableCell>{p.material}</TableCell>
                        <TableCell align="right">{isBoundary ? 'Semi-infinito' : `${p.nominal_d} nm`}</TableCell>
                        <TableCell>
                          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                            <Checkbox 
                              size="small" 
                              disabled={isBoundary} 
                              checked={p.enabled_d}
                              onChange={(e) => handlePerturbationChange(idx, 'enabled_d', e.target.checked)}
                            />
                            <TextField 
                              size="small" 
                              type="number"
                              variant="standard"
                              disabled={!p.enabled_d}
                              slotProps={{ htmlInput: { step: 0.1, min: 0 } }}
                              sx={{ width: 60 }}
                              value={p.std_d}
                              onChange={(e) => handlePerturbationChange(idx, 'std_d', e.target.value)}
                            />
                          </Stack>
                        </TableCell>
                        <TableCell>
                          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                            <Checkbox 
                              size="small" 
                              disabled={p.material === "Grafeno"} 
                              checked={p.enabled_n}
                              onChange={(e) => handlePerturbationChange(idx, 'enabled_n', e.target.checked)}
                            />
                            <TextField 
                              size="small" 
                              type="number"
                              variant="standard"
                              disabled={!p.enabled_n}
                              slotProps={{ htmlInput: { step: 0.001, min: 0 } }}
                              sx={{ width: 65 }}
                              value={p.std_n}
                              onChange={(e) => handlePerturbationChange(idx, 'std_n', e.target.value)}
                            />
                          </Stack>
                        </TableCell>
                        <TableCell>
                          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                            <Checkbox 
                              size="small" 
                              disabled={p.material === "Grafeno"} 
                              checked={p.enabled_k}
                              onChange={(e) => handlePerturbationChange(idx, 'enabled_k', e.target.checked)}
                            />
                            <TextField 
                              size="small" 
                              type="number"
                              variant="standard"
                              disabled={!p.enabled_k}
                              slotProps={{ htmlInput: { step: 0.001, min: 0 } }}
                              sx={{ width: 65 }}
                              value={p.std_k}
                              onChange={(e) => handlePerturbationChange(idx, 'std_k', e.target.value)}
                            />
                          </Stack>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <Paper variant="outlined" sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                Número de Iteraciones Monte Carlo
              </Typography>
              <Typography variant="h5" color="primary" sx={{ fontWeight: 'bold', mb: 2 }}>
                {runs} Corridas
              </Typography>
              <Slider
                value={runs}
                min={20}
                max={300}
                step={10}
                onChange={(_, val) => setRuns(val as number)}
                valueLabelDisplay="auto"
                sx={{ mb: 4 }}
              />

              <Button
                variant="contained"
                size="large"
                startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <PlayArrowIcon />}
                onClick={handleRunMonteCarlo}
                disabled={loading || layers.length === 0}
                sx={{ height: 48, fontWeight: 'bold' }}
              >
                {loading ? 'Ejecutando Simulación...' : 'Correr Monte Carlo'}
              </Button>
            </Paper>
          </Grid>
        </Grid>
      </Paper>

      {result && (
        <Box>
          {/* Yield Box and Stats Grid */}
          <Paper variant="outlined" sx={{ p: 3, mb: 4, bgcolor: result.stats.yield_percent >= 90 ? '#e8f5e9' : result.stats.yield_percent >= 70 ? '#fff3e0' : '#ffebee' }}>
            <Grid container spacing={3} sx={{ alignItems: 'center' }}>
              <Grid size={{ xs: 12, md: 5 }}>
                <Typography variant="subtitle2" color="textSecondary" sx={{ fontWeight: 'bold' }}>
                  RENDIMIENTO OPERATIVO (YIELD)
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 'bold', color: result.stats.yield_percent >= 90 ? 'success.main' : result.stats.yield_percent >= 70 ? 'warning.main' : 'error.main', my: 1 }}>
                  {result.stats.yield_percent.toFixed(1)}%
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                  {result.stats.yield_message}
                </Typography>
              </Grid>
              <Grid size={{ xs: 12, md: 7 }}>
                <Grid container spacing={2}>
                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Card variant="outlined">
                      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                        <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold' }}>PROMEDIO</Typography>
                        <Typography variant="h6" color="primary">{result.stats.mean.toFixed(isSpectral ? 1 : 3)} {unit}</Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Card variant="outlined">
                      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                        <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold' }}>DESV. ESTÁNDAR</Typography>
                        <Typography variant="h6" color="secondary">±{result.stats.std.toFixed(isSpectral ? 2 : 4)} {unit}</Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Card variant="outlined">
                      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                        <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold' }}>MEDIANA</Typography>
                        <Typography variant="h6" color="info.main">{result.stats.median.toFixed(isSpectral ? 1 : 3)} {unit}</Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid size={{ xs: 6, sm: 3 }}>
                    <Card variant="outlined">
                      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                        <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold' }}>I.C. DEL 95%</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 'bold', mt: 0.5 }}>
                          [{result.stats.ci_lower.toFixed(isSpectral ? 1 : 2)}, {result.stats.ci_upper.toFixed(isSpectral ? 1 : 2)}]
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                </Grid>
              </Grid>
            </Grid>
          </Paper>

          {/* Charts Row */}
          <Grid container spacing={4}>
            <Grid size={{ xs: 12, md: 7 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 2 }}>
                Variación de Curvas Ópticas (Envelope y 15 Corridas Aleatorias)
              </Typography>
              <Paper variant="outlined" sx={{ height: 400, p: 2, bgcolor: '#fff' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={curvesChartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="xVal" type="number" domain={isSpectral ? [400, 1000] : [30, 85]}>
                      <Label value={isSpectral ? "Longitud de Onda (nm)" : "Ángulo de Incidencia (deg)"} offset={-5} position="insideBottom" />
                    </XAxis>
                    <YAxis domain={[0, 1.0]}>
                      <Label value="Reflectancia (R)" angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} />
                    </YAxis>
                    <Tooltip labelFormatter={(label) => isSpectral ? `Wavelength: ${Number(label).toFixed(1)} nm` : `Ángulo: ${Number(label).toFixed(2)}°`} />
                    <Legend verticalAlign="top" height={36} />

                    {/* Spaghetti curves */}
                    {result.sample_curves.map((_, idx) => (
                      <Line
                        key={idx}
                        type="monotone"
                        dataKey={`sample_${idx}`}
                        stroke="#b0bec5"
                        strokeWidth={0.5}
                        opacity={0.35}
                        dot={false}
                        legendType="none"
                        isAnimationActive={false}
                      />
                    ))}

                    {/* Percentile Envelopes */}
                    <Line
                      type="monotone"
                      dataKey="p5"
                      name="Percentil 5%"
                      stroke="#ab47bc"
                      strokeWidth={1}
                      strokeDasharray="4 4"
                      dot={false}
                      isAnimationActive={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="p95"
                      name="Percentil 95%"
                      stroke="#ab47bc"
                      strokeWidth={1}
                      strokeDasharray="4 4"
                      dot={false}
                      isAnimationActive={false}
                    />

                    {/* Nominal curve */}
                    <Line
                      type="monotone"
                      dataKey="nominal"
                      name="Configuración Nominal"
                      stroke="#0d47a1"
                      strokeWidth={2.5}
                      dot={false}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </Paper>
            </Grid>

            <Grid size={{ xs: 12, md: 5 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 2 }}>
                Distribución del Punto de Resonancia
              </Typography>
              <Paper variant="outlined" sx={{ height: 400, p: 2, bgcolor: '#fff' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={histogramData} margin={{ top: 15, right: 10, left: 10, bottom: 15 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="binCenter" type="category">
                      <Label value={isSpectral ? "Longitud de onda resonante (nm)" : "Ángulo resonante (deg)"} offset={-5} position="insideBottom" />
                    </XAxis>
                    <YAxis>
                      <Label value="Frecuencia (conteo)" angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} />
                    </YAxis>
                    <Tooltip formatter={(value) => [value, 'Corridas']} />
                    <Bar dataKey="Frecuencia" fill="#8884d8" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                    
                    {/* Mark nominal resonance */}
                    <ReferenceLine x={result.stats.mean} stroke="#d32f2f" strokeWidth={1.5} label={{ value: 'Media', position: 'top', fill: '#d32f2f', fontSize: 10 }} />
                  </BarChart>
                </ResponsiveContainer>
              </Paper>
            </Grid>
          </Grid>
        </Box>
      )}
    </Box>
  );
};

export default MonteCarloPanel;
