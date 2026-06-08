import React, { useState, useEffect } from 'react';
import { 
  Box, Button, CircularProgress, Stack, Paper, Typography, 
  Grid, Card, Alert, Table, TableBody, TableCell, TableContainer, 
  TableHead, TableRow, TextField, MenuItem
} from '@mui/material';
import TimelineIcon from '@mui/icons-material/Timeline';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import { 
  ComposedChart, Scatter, Line, XAxis, YAxis, CartesianGrid, Tooltip, 
  Legend, ResponsiveContainer, Label 
} from 'recharts';
import { simulateCalibration } from '../api/client';
import type { LayerConfig, CalibrationResponse } from '../types';

interface Props {
  layers: LayerConfig[];
  wavelength: number;
  polarization: 'TM' | 'TE';
  interrogationMode: 'angular' | 'spectral';
  fixedAngle: number;
}

const CalibrationCurvePanel: React.FC<Props> = ({ 
  layers, wavelength, polarization, interrogationMode, fixedAngle 
}) => {
  const [nStart, setNStart] = useState<number>(1.330);
  const [nEnd, setNEnd] = useState<number>(1.350);
  const [steps, setSteps] = useState<number>(5);
  const [noise, setNoise] = useState<number>(0.001); // Standard noise in deg or nm

  const [calibData, setCalibData] = useState<CalibrationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSimulateCalibration = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await simulateCalibration({
        layers,
        wavelength_nm: wavelength,
        polarization,
        interrogation_mode: interrogationMode,
        fixed_angle_deg: fixedAngle,
        n_start: nStart,
        n_end: nEnd,
        steps: steps
      });
      setCalibData(res);
    } catch (err: any) {
      console.error(err);
      setErrorMsg("Error al generar la curva de calibración. Verifica los límites de refracción.");
    } finally {
      setLoading(false);
    }
  };

  // Automatically recalculate if layers or configuration changes to keep data consistent
  useEffect(() => {
    if (calibData) {
      handleSimulateCalibration();
    }
  }, [layers, wavelength, polarization, interrogationMode, fixedAngle]);

  // Estimate Limit of Detection (LoD)
  let lod: number | null = null;
  if (calibData && calibData.slope !== 0) {
    // LoD = 3 * noise / S
    lod = Math.abs((3 * noise) / calibData.slope);
  }

  // Format data for Recharts ComposedChart
  const chartData = calibData ? calibData.points.map((pt, idx) => ({
    n: pt.n,
    measured: pt.resonance_value,
    fit: calibData.fit_line[idx]
  })) : [];

  const yAxisLabel = interrogationMode === 'angular' ? "Ángulo de Resonancia (°)" : "Longitud de Onda de Resonancia (nm)";
  const slopeUnit = interrogationMode === 'angular' ? "°/RIU" : "nm/RIU";

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Controls Column */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', mb: 2 }}>
              <TimelineIcon color="primary" />
              <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                Parámetros de Calibración
              </Typography>
            </Stack>

            <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
              Simula el desplazamiento del dip de resonancia al variar linealmente el índice de refracción del analito.
            </Typography>

            <Stack spacing={2.5}>
              <TextField
                label="Índice Inicial (n_min)"
                type="number"
                slotProps={{ htmlInput: { step: 0.005, min: 1.0, max: 2.0 } }}
                value={nStart}
                onChange={(e) => setNStart(parseFloat(e.target.value) || 1.33)}
                fullWidth
                size="small"
              />

              <TextField
                label="Índice Final (n_max)"
                type="number"
                slotProps={{ htmlInput: { step: 0.005, min: 1.0, max: 2.0 } }}
                value={nEnd}
                onChange={(e) => setNEnd(parseFloat(e.target.value) || 1.35)}
                fullWidth
                size="small"
              />

              <TextField
                select
                label="Puntos de Calibración"
                value={steps}
                onChange={(e) => setSteps(parseInt(e.target.value as string, 10))}
                fullWidth
                size="small"
              >
                {[3, 5, 7, 10, 15, 20].map((opt) => (
                  <MenuItem key={opt} value={opt}>
                    {opt} puntos
                  </MenuItem>
                ))}
              </TextField>

              <TextField
                label={interrogationMode === 'angular' ? "Ruido del Sistema (deg)" : "Ruido del Sistema (nm)"}
                type="number"
                slotProps={{ htmlInput: { step: 0.0001, min: 0.0001 } }}
                value={noise}
                onChange={(e) => setNoise(parseFloat(e.target.value) || 0.001)}
                fullWidth
                size="small"
                helperText="Nivel de ruido típico para estimar el LoD"
              />

              <Button
                variant="contained"
                color="primary"
                onClick={handleSimulateCalibration}
                disabled={loading || nStart >= nEnd}
                startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <ShowChartIcon />}
                fullWidth
                sx={{ mt: 1, fontWeight: 'bold' }}
              >
                {loading ? "Simulando..." : "Calibrar Sensor"}
              </Button>
            </Stack>
          </Paper>

          {errorMsg && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {errorMsg}
            </Alert>
          )}
        </Grid>

        {/* Results Column */}
        <Grid size={{ xs: 12, md: 8 }}>
          {calibData ? (
            <Stack spacing={3}>
              {/* Metrics Row */}
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <Card variant="outlined" sx={{ p: 2, textAlign: 'center', bgcolor: '#e8f5e9' }}>
                    <Typography variant="body2" color="textSecondary" sx={{ fontWeight: 'bold' }}>
                      Sensibilidad (S)
                    </Typography>
                    <Typography variant="h5" sx={{ fontWeight: 'bold', color: '#2e7d32', mt: 0.5 }}>
                      {calibData.slope.toFixed(2)} {slopeUnit}
                    </Typography>
                  </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <Card variant="outlined" sx={{ p: 2, textAlign: 'center', bgcolor: '#e3f2fd' }}>
                    <Typography variant="body2" color="textSecondary" sx={{ fontWeight: 'bold' }}>
                      Linealidad (R²)
                    </Typography>
                    <Typography variant="h5" sx={{ fontWeight: 'bold', color: '#1565c0', mt: 0.5 }}>
                      {calibData.r_squared.toFixed(5)}
                    </Typography>
                  </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <Card variant="outlined" sx={{ p: 2, textAlign: 'center', bgcolor: '#fff8e1' }}>
                    <Typography variant="body2" color="textSecondary" sx={{ fontWeight: 'bold' }}>
                      Límite de Detección (LoD)
                    </Typography>
                    <Typography variant="h5" sx={{ fontWeight: 'bold', color: '#f57f17', mt: 0.5 }}>
                      {lod ? lod.toExponential(3) : 'N/A'} RIU
                    </Typography>
                  </Card>
                </Grid>
              </Grid>

              {/* Chart */}
              <Paper variant="outlined" sx={{ height: 350, p: 2, bgcolor: '#fff' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis 
                      dataKey="n" 
                      type="number" 
                      domain={['auto', 'auto']}
                      tickFormatter={(v) => v.toFixed(3)}
                    >
                      <Label value="Índice de Refracción del Analito (n)" offset={-10} position="insideBottom" />
                    </XAxis>
                    <YAxis domain={['auto', 'auto']}>
                      <Label value={yAxisLabel} angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} />
                    </YAxis>
                    <Tooltip formatter={(value: any) => [Number(value).toFixed(4), '']} />
                    <Legend verticalAlign="top" height={36} />
                    <Scatter name="Puntos Medidos" dataKey="measured" fill="#d32f2f" line={false} />
                    <Line name="Regresión Lineal" dataKey="fit" stroke="#1976d2" strokeWidth={2} dot={false} activeDot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </Paper>

              {/* Table */}
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead sx={{ bgcolor: '#f5f5f5' }}>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 'bold' }}>Índice Analito (n)</TableCell>
                      <TableCell sx={{ fontWeight: 'bold' }}>Resonancia</TableCell>
                      <TableCell sx={{ fontWeight: 'bold' }}>Desplazamiento (Δ)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {calibData.points.map((pt, idx) => (
                      <TableRow key={idx}>
                        <TableCell>{pt.n.toFixed(4)}</TableCell>
                        <TableCell>
                          {pt.resonance_value.toFixed(4)} {interrogationMode === 'angular' ? '°' : 'nm'}
                        </TableCell>
                        <TableCell>
                          {pt.shift >= 0 ? `+${pt.shift.toFixed(4)}` : pt.shift.toFixed(4)} {interrogationMode === 'angular' ? '°' : 'nm'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Stack>
          ) : (
            <Paper variant="outlined" sx={{ p: 5, textAlign: 'center', color: 'text.secondary' }}>
              <Typography variant="body1">
                Haz clic en <strong>Calibrar Sensor</strong> para iniciar la simulación y graficar la curva.
              </Typography>
            </Paper>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default CalibrationCurvePanel;
