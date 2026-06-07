import React, { useState, useEffect } from 'react';
import { 
  Box, Button, CircularProgress, Slider, Stack, Paper, Typography, 
  Grid, Card, Alert, Table, TableBody, TableCell, TableContainer, 
  TableHead, TableRow 
} from '@mui/material';
import ThermostatIcon from '@mui/icons-material/Thermostat';
import RotateLeftIcon from '@mui/icons-material/RotateLeft';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, 
  Legend, ResponsiveContainer, Label 
} from 'recharts';
import { simulateReflectance, simulateThermalSweep } from '../api/client';
import type { LayerConfig, ThermalSweepResponse, ReflectanceResponse } from '../types';

interface Props {
  layers: LayerConfig[];
  wavelength: number;
  polarization: 'TM' | 'TE';
  interrogationMode: 'angular' | 'spectral';
  fixedAngle: number;
}

const getColorForTemp = (temp: number) => {
  if (temp <= 10) return '#2196f3'; // Cold Blue
  if (temp <= 20) return '#03a9f4'; // Light Blue
  if (temp <= 30) return '#4caf50'; // Green
  if (temp <= 40) return '#ff9800'; // Orange
  if (temp <= 50) return '#ff5722'; // Dark Orange
  return '#f44336'; // Hot Red
};

const ThermalAnalysisPanel: React.FC<Props> = ({ 
  layers, wavelength, polarization, interrogationMode, fixedAngle 
}) => {
  const [temperature, setTemperature] = useState<number>(25.0);
  const [liveCurve, setLiveCurve] = useState<ReflectanceResponse | null>(null);
  const [sweepData, setSweepData] = useState<ThermalSweepResponse | null>(null);
  const [loadingSweep, setLoadingSweep] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Simulate single temperature curve (live update on slider change)
  const fetchLiveCurve = async (tempVal: number) => {
    try {
      const res = await simulateReflectance({
        layers,
        wavelength_nm: wavelength,
        polarization,
        interrogation_mode: interrogationMode,
        fixed_angle_deg: fixedAngle,
        temperature_c: tempVal
      });
      setLiveCurve(res);
      setErrorMsg(null);
    } catch (err: any) {
      console.error(err);
      setErrorMsg("Error en la simulación térmica en tiempo real.");
    }
  };

  // Debounce / Trigger live simulation on slider release or value change
  useEffect(() => {
    fetchLiveCurve(temperature);
  }, [temperature, layers, wavelength, polarization, interrogationMode, fixedAngle]);

  const handleSweep = async () => {
    setLoadingSweep(true);
    setErrorMsg(null);
    try {
      const res = await simulateThermalSweep({
        layers,
        wavelength_nm: wavelength,
        polarization,
        interrogation_mode: interrogationMode,
        fixed_angle_deg: fixedAngle
      });
      setSweepData(res);
    } catch (err: any) {
      console.error(err);
      setErrorMsg("Error al generar el barrido térmico.");
    } finally {
      setLoadingSweep(false);
    }
  };

  // Re-generate sweep automatically if configuration changes to keep UI synchronized
  useEffect(() => {
    if (sweepData) {
      handleSweep();
    }
  }, [layers, wavelength, polarization, interrogationMode, fixedAngle]);

  // Calculate thermal sensitivity
  let thermalSensitivity = 0;
  let sUnit = interrogationMode === 'angular' ? 'deg/°C' : 'nm/°C';
  if (sweepData && sweepData.curves.length >= 2) {
    const sorted = [...sweepData.curves].sort((a, b) => a.temperature_c - b.temperature_c);
    const cMin = sorted[0];
    const cMax = sorted[sorted.length - 1];
    const deltaT = cMax.temperature_c - cMin.temperature_c;

    if (interrogationMode === 'angular' && cMin.resonance_angle !== undefined && cMax.resonance_angle !== undefined) {
      thermalSensitivity = (cMax.resonance_angle - cMin.resonance_angle) / deltaT;
    } else if (interrogationMode === 'spectral' && cMin.resonance_wavelength !== undefined && cMax.resonance_wavelength !== undefined) {
      thermalSensitivity = (cMax.resonance_wavelength - cMin.resonance_wavelength) / deltaT;
    }
  }

  // Format chart data
  const xVals = sweepData 
    ? (sweepData.angles || sweepData.wavelengths || []) 
    : (liveCurve ? (liveCurve.angles || liveCurve.wavelengths || []) : []);

  const chartData = xVals.map((x, idx) => {
    const row: any = { xVal: x };
    
    // Include live curve
    if (liveCurve && liveCurve.reflectance && liveCurve.reflectance[idx] !== undefined) {
      row.live = liveCurve.reflectance[idx];
    }
    
    // Include sweep curves
    if (sweepData) {
      sweepData.curves.forEach((c) => {
        row[`temp_${c.temperature_c}`] = c.reflectance[idx];
      });
    }
    return row;
  });

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Controls Column */}
        <Grid size={{ xs: 12, md: 4 }}>
          {/* Temperature Slider */}
          <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', mb: 2 }}>
              <ThermostatIcon color="primary" />
              <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                Control de Temperatura Live
              </Typography>
            </Stack>

            <Typography variant="body2" color="textSecondary" sx={{ mb: 1 }}>
              Desliza para simular la reflectancia en tiempo real:
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 'bold', color: 'primary.main', mb: 2 }}>
              {temperature.toFixed(1)} °C
            </Typography>

            <Slider
              value={temperature}
              min={10}
              max={60}
              step={0.5}
              onChange={(_, val) => setTemperature(val as number)}
              valueLabelDisplay="auto"
              sx={{ color: getColorForTemp(temperature) }}
            />
            
            <Stack direction="row" sx={{ mt: 1, mb: 2, justifyContent: 'space-between' }}>
              <Typography variant="caption" color="textSecondary">10 °C (Frío)</Typography>
              <Typography variant="caption" color="textSecondary">60 °C (Caliente)</Typography>
            </Stack>

            {liveCurve && (
              <Box sx={{ p: 1.5, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                <Typography variant="caption" color="textSecondary" sx={{ display: 'block' }}>
                  Ángulo Crítico estimado: ~{(61.6 + 0.003 * (temperature - 20)).toFixed(2)}°
                </Typography>
                <Typography variant="caption" color="textSecondary" sx={{ display: 'block' }}>
                  Resonancia @ {temperature}°C: <strong>
                    {interrogationMode === 'angular' 
                      ? `${liveCurve.resonance_angle?.toFixed(3)}°` 
                      : `${liveCurve.resonance_wavelength?.toFixed(1)} nm`}
                  </strong>
                </Typography>
              </Box>
            )}
          </Paper>

          {/* Thermal Sweep Trigger */}
          <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
            <Typography variant="body1" sx={{ fontWeight: 'bold', mb: 1 }}>
              Barrido Térmico Completo
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
              Calcula y superpone una familia de curvas de resonancia desde 10°C hasta 60°C para evaluar la deriva térmica.
            </Typography>

            <Button
              variant="contained"
              fullWidth
              onClick={handleSweep}
              disabled={loadingSweep}
              startIcon={loadingSweep ? <CircularProgress size={20} color="inherit" /> : <RotateLeftIcon />}
              sx={{ py: 1, fontWeight: 'bold' }}
            >
              {loadingSweep ? 'Simulando Barrido...' : 'Simular Barrido Térmico'}
            </Button>
          </Paper>

          {/* Thermal Analysis Details */}
          {sweepData && (
            <Card variant="outlined" sx={{ p: 2.5, borderLeft: '5px solid #ff9800', bgcolor: '#fffde7' }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1.5, color: 'warning.dark' }}>
                Estabilidad Térmica del Sensor
              </Typography>
              
              <Typography variant="body2" sx={{ mb: 2 }}>
                Deriva térmica calculada (Sensibilidad térmica):
                <Box component="span" sx={{ display: 'block', variant: 'h5', fontWeight: 'bold', my: 1, color: 'warning.main' }}>
                  {thermalSensitivity.toExponential(4)} {sUnit}
                </Box>
              </Typography>

              <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 200, mb: 1.5 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 'bold', fontSize: 10 }}>Temp (°C)</TableCell>
                      <TableCell sx={{ fontWeight: 'bold', fontSize: 10 }}>Resonancia</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {sweepData.curves.map((c) => (
                      <TableRow key={c.temperature_c}>
                        <TableCell sx={{ fontSize: 11 }}>{c.temperature_c} °C</TableCell>
                        <TableCell sx={{ fontSize: 11, fontWeight: 'bold', color: getColorForTemp(c.temperature_c) }}>
                          {interrogationMode === 'angular' 
                            ? `${c.resonance_angle?.toFixed(3)}°` 
                            : `${c.resonance_wavelength?.toFixed(1)} nm`}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>

              <Typography variant="caption" color="textSecondary" sx={{ display: 'block' }}>
                <strong>Análisis Físico:</strong> El agua líquida tiene un dn/dT negativo (aprox. -8e-5 K^-1), lo que desplaza la curva de resonancia hacia <strong>ángulos más bajos</strong> o <strong>longitudes de onda más cortas</strong> a medida que la celda se calienta.
              </Typography>
            </Card>
          )}

          {errorMsg && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {errorMsg}
            </Alert>
          )}
        </Grid>

        {/* Chart Column */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Paper variant="outlined" sx={{ p: 2.5, height: '100%', minHeight: 480, display: 'flex', flexDirection: 'column' }}>
            <Typography variant="body1" sx={{ fontWeight: 'bold', mb: 2 }}>
              Análisis Termo-Óptico: Reflectancia vs Temperatura
            </Typography>

            <Box sx={{ flexGrow: 1, height: 420 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 15, right: 30, left: 10, bottom: 25 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis 
                    dataKey="xVal" 
                    type="number"
                    domain={interrogationMode === 'spectral' ? [400, 1000] : [30, 85]}
                    tick={{ fontSize: 11 }}
                  >
                    <Label value={interrogationMode === 'angular' ? "Ángulo de Incidencia (deg)" : "Longitud de Onda (nm)"} offset={-15} position="insideBottom" />
                  </XAxis>
                  <YAxis domain={[0, 1.05]} tick={{ fontSize: 11 }}>
                    <Label value="Reflectancia (R)" angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} />
                  </YAxis>
                  <Tooltip 
                    formatter={(val: any) => Number(val).toFixed(5)}
                    labelFormatter={(label: any) => `X: ${Number(label).toFixed(2)}`}
                  />
                  <Legend verticalAlign="top" height={36} />

                  {/* Render live temperature line */}
                  <Line 
                    type="monotone" 
                    dataKey="live" 
                    name={`T_activa (${temperature.toFixed(1)} °C)`}
                    stroke="#ff33cc" 
                    dot={false}
                    strokeWidth={3}
                    strokeDasharray="4 4"
                  />

                  {/* Render thermal sweep family lines */}
                  {sweepData && sweepData.curves.map((curve) => (
                    <Line 
                      key={curve.temperature_c}
                      type="monotone" 
                      dataKey={`temp_${curve.temperature_c}`} 
                      name={`${curve.temperature_c} °C`} 
                      stroke={getColorForTemp(curve.temperature_c)} 
                      dot={false}
                      strokeWidth={1.5}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default ThermalAnalysisPanel;
