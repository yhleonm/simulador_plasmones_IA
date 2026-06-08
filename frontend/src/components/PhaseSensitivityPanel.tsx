import React, { useState, useEffect } from 'react';
import { 
  Box, Button, CircularProgress, Stack, Paper, Typography, 
  Grid, Card, Alert, TextField, Divider
} from '@mui/material';
import TuneIcon from '@mui/icons-material/Tune';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, 
  Legend, ResponsiveContainer, ReferenceLine, Label
} from 'recharts';
import { simulatePhaseSensitivity } from '../api/client';
import type { LayerConfig, PhaseSensitivityResponse } from '../types';

interface Props {
  layers: LayerConfig[];
  wavelength: number;
  polarization: 'TM' | 'TE';
  interrogationMode: 'angular' | 'spectral';
  fixedAngle: number;
}

const PhaseSensitivityPanel: React.FC<Props> = ({ 
  layers, wavelength, polarization, interrogationMode, fixedAngle 
}) => {
  const [deltaN, setDeltaN] = useState<number>(0.0001);
  const [sensitivityData, setSensitivityData] = useState<PhaseSensitivityResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSimulateSensitivity = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await simulatePhaseSensitivity({
        layers,
        wavelength_nm: wavelength,
        polarization,
        interrogation_mode: interrogationMode,
        fixed_angle_deg: fixedAngle,
        delta_n: deltaN
      });
      setSensitivityData(res);
    } catch (err: any) {
      console.error(err);
      setErrorMsg("Error al calcular la sensibilidad de fase. Verifica la configuración de capas.");
    } finally {
      setLoading(false);
    }
  };

  // Automatically recalculate when inputs change
  useEffect(() => {
    handleSimulateSensitivity();
  }, [layers, wavelength, polarization, interrogationMode, fixedAngle]);

  const xLabel = interrogationMode === 'angular' ? "Ángulo θ (°)" : "Longitud de onda λ (nm)";
  const xUnit = interrogationMode === 'angular' ? "°" : "nm";

  // Prepare chart data
  const chartData = sensitivityData ? sensitivityData.x_grid.map((x, idx) => ({
    x,
    phaseNominal: sensitivityData.phase_nominal[idx],
    phasePerturbed: sensitivityData.phase_perturbed[idx],
    reflectanceNominal: sensitivityData.reflectance_nominal[idx],
    derivativePhase: sensitivityData.derivative_phase[idx],
    derivativeIntensity: sensitivityData.derivative_intensity[idx],
  })) : [];

  // Calculate amplification factor
  let amplificationFactor = 0;
  if (sensitivityData && sensitivityData.max_intensity_sensitivity !== 0) {
    amplificationFactor = Math.abs(sensitivityData.max_phase_sensitivity) / Math.abs(sensitivityData.max_intensity_sensitivity);
  }

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Controls Column */}
        <Grid size={{ xs: 12, md: 3 }}>
          <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', mb: 2 }}>
              <TuneIcon color="primary" />
              <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                Parámetros de Sensibilidad
              </Typography>
            </Stack>

            <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
              Calcula la derivada de la fase respecto al índice del analito por diferencia finita. Se perturba el índice de la última capa por Δn.
            </Typography>

            <Stack spacing={2.5}>
              <TextField
                label="Perturbación del Analito (Δn)"
                type="number"
                slotProps={{ htmlInput: { step: 0.0001, min: 0.00001, max: 0.01 } }}
                value={deltaN}
                onChange={(e) => setDeltaN(parseFloat(e.target.value) || 0.0001)}
                fullWidth
                size="small"
                helperText="Paso de derivación (delta n)"
              />

              <Button
                variant="contained"
                color="primary"
                onClick={handleSimulateSensitivity}
                disabled={loading}
                fullWidth
                startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <ShowChartIcon />}
              >
                {loading ? "Simulando..." : "Calcular Sensibilidad"}
              </Button>

              <Divider sx={{ my: 1 }} />

              <Box sx={{ bgcolor: 'rgba(21, 101, 192, 0.04)', p: 1.5, borderRadius: 1.5, border: '1px solid rgba(21, 101, 192, 0.1)' }}>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
                  <InfoOutlinedIcon fontSize="small" color="primary" />
                  <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
                    Nota Física
                  </Typography>
                </Stack>
                <Typography variant="caption" color="textSecondary" component="p">
                  En la resonancia de plasmones (SPR), la fase sufre una transición abrupta mientras que la reflectancia exhibe un mínimo. 
                  La derivada d(Δφ)/dn alcanza valores del orden de 100 a 1000 rad/RIU, superando por mucho a la derivada de intensidad dR/dn.
                </Typography>
              </Box>
            </Stack>
          </Paper>
        </Grid>

        {/* Results & Plots Column */}
        <Grid size={{ xs: 12, md: 9 }}>
          {errorMsg && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {errorMsg}
            </Alert>
          )}

          {sensitivityData && (
            <Stack spacing={3}>
              {/* KPIs Summary Cards */}
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <Card variant="outlined" sx={{ p: 2, textAlign: 'center', borderLeft: '5px solid #8884d8' }}>
                    <Typography variant="caption" color="textSecondary" sx={{ textTransform: 'uppercase', fontWeight: 'bold' }}>
                      Máx. Sensibilidad de Fase
                    </Typography>
                    <Typography variant="h4" sx={{ fontWeight: 'bold', my: 1, color: '#8884d8' }}>
                      {sensitivityData.max_phase_sensitivity.toFixed(2)}
                    </Typography>
                    <Typography variant="caption" color="textSecondary" component="div">
                      rad/RIU en {sensitivityData.max_phase_sensitivity_x.toFixed(3)}{xUnit}
                    </Typography>
                    <Typography variant="caption" color="textSecondary" component="div">
                      ({(sensitivityData.max_phase_sensitivity * 180 / Math.PI).toFixed(1)} °/RIU)
                    </Typography>
                  </Card>
                </Grid>

                <Grid size={{ xs: 12, sm: 4 }}>
                  <Card variant="outlined" sx={{ p: 2, textAlign: 'center', borderLeft: '5px solid #ff7300' }}>
                    <Typography variant="caption" color="textSecondary" sx={{ textTransform: 'uppercase', fontWeight: 'bold' }}>
                      Máx. Sensibilidad de Intensidad
                    </Typography>
                    <Typography variant="h4" sx={{ fontWeight: 'bold', my: 1, color: '#ff7300' }}>
                      {sensitivityData.max_intensity_sensitivity.toFixed(2)}
                    </Typography>
                    <Typography variant="caption" color="textSecondary" component="div">
                      1/RIU en {sensitivityData.max_intensity_sensitivity_x.toFixed(3)}{xUnit}
                    </Typography>
                  </Card>
                </Grid>

                <Grid size={{ xs: 12, sm: 4 }}>
                  <Card variant="outlined" sx={{ p: 2, textAlign: 'center', borderLeft: '5px solid #009688', bgcolor: 'rgba(0, 150, 136, 0.02)' }}>
                    <Stack direction="row" spacing={0.5} sx={{ justifyContent: 'center', alignItems: 'center' }}>
                      <CompareArrowsIcon sx={{ color: '#009688' }} />
                      <Typography variant="caption" color="textSecondary" sx={{ textTransform: 'uppercase', fontWeight: 'bold' }}>
                        Factor de Amplificación
                      </Typography>
                    </Stack>
                    <Typography variant="h4" sx={{ fontWeight: 'bold', my: 1, color: '#009688' }}>
                      {amplificationFactor.toFixed(1)}x
                    </Typography>
                    <Typography variant="caption" color="textSecondary" component="div">
                      Mejora en límite de detección interferométrico
                    </Typography>
                  </Card>
                </Grid>
              </Grid>

              {/* Chart 1: Phase Difference & Reflectance Profile */}
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 2 }}>
                  Transición de Fase y Curva de Reflectancia (Nominal)
                </Typography>
                <Box sx={{ width: '100%', height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="x" type="number" domain={['auto', 'auto']}>
                        <Label value={xLabel} offset={-5} position="insideBottom" />
                      </XAxis>
                      <YAxis yAxisId="left" domain={[-Math.PI - 0.2, Math.PI + 0.2]}>
                        <Label value="Diferencia de Fase Δφ (rad)" angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} />
                      </YAxis>
                      <YAxis yAxisId="right" orientation="right" domain={[0, 1.1]}>
                        <Label value="Reflectancia (R)" angle={90} position="insideRight" style={{ textAnchor: 'middle' }} />
                      </YAxis>
                      <Tooltip 
                        formatter={(value: any, name: any) => {
                          if (name.includes("Phase")) return [`${Number(value).toFixed(4)} rad`, name];
                          return [`${Number(value).toFixed(4)}`, name];
                        }}
                        labelFormatter={(label) => `${xLabel}: ${Number(label).toFixed(3)}`}
                      />
                      <Legend verticalAlign="top" height={36} />
                      
                      <ReferenceLine yAxisId="left" y={0} stroke="#ccc" strokeDasharray="3 3" />
                      {/* Highlight the angle of maximum phase sensitivity */}
                      <ReferenceLine 
                        yAxisId="left"
                        x={sensitivityData.max_phase_sensitivity_x} 
                        stroke="#8884d8" 
                        strokeDasharray="5 5" 
                        label={{ value: 'Máx. Sens. Fase', position: 'top', fill: '#8884d8', fontSize: 11 }} 
                      />

                      <Line 
                        yAxisId="left" 
                        type="monotone" 
                        dataKey="phaseNominal" 
                        stroke="#8884d8" 
                        strokeWidth={2.5} 
                        name="Fase Nominal (Δφ)" 
                        dot={false} 
                      />
                      <Line 
                        yAxisId="left" 
                        type="monotone" 
                        dataKey="phasePerturbed" 
                        stroke="#b19ffb" 
                        strokeWidth={1.5} 
                        strokeDasharray="4 4"
                        name="Fase Perturbada (Δφ + Δn)" 
                        dot={false} 
                      />
                      <Line 
                        yAxisId="right" 
                        type="monotone" 
                        dataKey="reflectanceNominal" 
                        stroke="#0088fe" 
                        strokeWidth={2} 
                        name="Reflectancia R" 
                        dot={false} 
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </Box>
              </Paper>

              {/* Chart 2: Derivatives (Sensitivity Curves) */}
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 2 }}>
                  Curvas de Sensibilidad Diferencial (Derivadas d(Δφ)/dn y dR/dn)
                </Typography>
                <Box sx={{ width: '100%', height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="x" type="number" domain={['auto', 'auto']}>
                        <Label value={xLabel} offset={-5} position="insideBottom" />
                      </XAxis>
                      <YAxis yAxisId="left">
                        <Label value="Sensibilidad de Fase d(Δφ)/dn (rad/RIU)" angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} />
                      </YAxis>
                      <YAxis yAxisId="right" orientation="right">
                        <Label value="Sensibilidad de Reflectancia dR/dn (1/RIU)" angle={90} position="insideRight" style={{ textAnchor: 'middle' }} />
                      </YAxis>
                      <Tooltip 
                        formatter={(value: any, name: any) => [`${Number(value).toFixed(2)}`, name]}
                        labelFormatter={(label) => `${xLabel}: ${Number(label).toFixed(3)}`}
                      />
                      <Legend verticalAlign="top" height={36} />
                      
                      <ReferenceLine 
                        yAxisId="left"
                        x={sensitivityData.max_phase_sensitivity_x} 
                        stroke="#8884d8" 
                        strokeDasharray="5 5" 
                      />
                      <ReferenceLine 
                        yAxisId="right"
                        x={sensitivityData.max_intensity_sensitivity_x} 
                        stroke="#ff7300" 
                        strokeDasharray="5 5" 
                      />

                      <Line 
                        yAxisId="left" 
                        type="monotone" 
                        dataKey="derivativePhase" 
                        stroke="#8884d8" 
                        strokeWidth={2.5} 
                        name="Sensibilidad de Fase d(Δφ)/dn" 
                        dot={false} 
                      />
                      <Line 
                        yAxisId="right" 
                        type="monotone" 
                        dataKey="derivativeIntensity" 
                        stroke="#ff7300" 
                        strokeWidth={2} 
                        name="Sensibilidad de Reflectancia dR/dn" 
                        dot={false} 
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </Box>
              </Paper>
            </Stack>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default PhaseSensitivityPanel;
