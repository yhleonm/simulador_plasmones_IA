import React, { useState, useEffect } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { 
  Box, Button, CircularProgress, Typography, Paper, Stack, Divider, 
  ToggleButton, ToggleButtonGroup, Card, CardContent, Alert, AlertTitle, Grid
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import TimelineIcon from '@mui/icons-material/Timeline';
import SpeedIcon from '@mui/icons-material/Speed';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

import { simulateLRSPPSweep } from '../api/client';
import type { LayerConfig, LRSPPSweepResponse } from '../types';

interface Props {
  layers: LayerConfig[];
  wavelength: number;
  polarization: 'TM' | 'TE';
}

const LRSPPPanel: React.FC<Props> = ({ layers, wavelength, polarization }) => {
  const [sweepType, setSweepType] = useState<'metal_thickness' | 'buffer_index'>('metal_thickness');
  const [data, setData] = useState<LRSPPSweepResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const runSweep = async () => {
    setLoading(true);
    try {
      const res = await simulateLRSPPSweep({
        layers,
        wavelength_nm: wavelength,
        polarization,
        sweep_type: sweepType,
        temperature_c: 20.0
      });
      setData(res);
    } catch (error: any) {
      console.error("LRSPP sweep failed", error);
      alert("Error en el barrido LRSPP: " + (error.message || "Error desconocido"));
    }
    setLoading(false);
  };

  useEffect(() => {
    runSweep();
  }, [sweepType, layers, wavelength, polarization]);

  // Encontrar el valor máximo de longitud de propagación
  const maxPropLength = data ? Math.max(...data.propagation_lengths) : 0;
  const maxPropIndex = data ? data.propagation_lengths.indexOf(maxPropLength) : -1;
  const optimalValue = data && maxPropIndex !== -1 ? data.sweep_values[maxPropIndex] : 0;
  const maxPenDepth = data && maxPropIndex !== -1 ? data.penetration_depths[maxPropIndex] : 0;
  const hasActiveLRSPP = data ? data.is_lrspp.some(v => v) : false;

  const chartData = data 
    ? data.sweep_values.map((val, idx) => ({
        value: val,
        L_prop: data.propagation_lengths[idx],
        L_pen: data.penetration_depths[idx]
      }))
    : [];

  return (
    <Box>
      <Stack direction="row" spacing={2} sx={{ mb: 3, alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 'bold', color: 'primary.main', display: 'flex', alignItems: 'center', gap: 1 }}>
            <TimelineIcon /> Plasmón de Rango Largo (LRSPP) y Longitud de Propagación
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Analiza cómo viaja la onda plasmónica lateralmente y su acoplamiento de bajas pérdidas
          </Typography>
        </Box>
        
        <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
          <ToggleButtonGroup
            value={sweepType}
            exclusive
            onChange={(_, val) => { if (val) setSweepType(val); }}
            size="small"
            color="primary"
          >
            <ToggleButton value="metal_thickness" sx={{ textTransform: 'none', fontWeight: 'bold' }}>
              Barrido de Espesor del Metal
            </ToggleButton>
            <ToggleButton value="buffer_index" sx={{ textTransform: 'none', fontWeight: 'bold' }}>
              Barrido de Simetría del Buffer
            </ToggleButton>
          </ToggleButtonGroup>
          <Button 
            variant="contained" 
            onClick={runSweep} 
            disabled={loading}
            size="small"
            sx={{ fontWeight: 'bold' }}
          >
            {loading ? <CircularProgress size={20} /> : 'Recalcular'}
          </Button>
        </Stack>
      </Stack>

      <Divider sx={{ mb: 3 }} />

      {/* Tarjetas de Métricas Físicas */}
      {data && (
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card variant="outlined" sx={{ borderLeft: '5px solid #2e7d32', height: '100%' }}>
              <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold', display: 'block', textTransform: 'uppercase' }}>
                  Longitud de Propagación Máxima (L_prop)
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 'bold', my: 1, color: 'success.main' }}>
                  {maxPropLength.toFixed(1)} µm
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  Distancia que viaja la onda antes de disiparse (1/e de intensidad).
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card variant="outlined" sx={{ borderLeft: '5px solid #1976d2', height: '100%' }}>
              <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold', display: 'block', textTransform: 'uppercase' }}>
                  Punto de Optimización Óptimo
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 'bold', my: 1, color: 'primary.main' }}>
                  {sweepType === 'metal_thickness' ? `${optimalValue.toFixed(1)} nm` : `n = ${optimalValue.toFixed(3)}`}
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  {sweepType === 'metal_thickness' 
                    ? 'Espesor de la capa de metal que maximiza la longitud.' 
                    : 'Índice de refracción del buffer que maximiza el acoplamiento.'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card variant="outlined" sx={{ borderLeft: '5px solid #9c27b0', height: '100%' }}>
              <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold', display: 'block', textTransform: 'uppercase' }}>
                  Penetración en el Analito (L_pen)
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 'bold', my: 1, color: 'secondary.main' }}>
                  {maxPenDepth > 0 ? `${maxPenDepth.toFixed(0)} nm` : 'N/A'}
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  Profundidad de decaimiento del campo en el superstrato analito.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card variant="outlined" sx={{ borderLeft: `5px solid ${hasActiveLRSPP ? '#ed6c02' : '#757575'}`, height: '100%' }}>
              <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold', display: 'block', textTransform: 'uppercase' }}>
                  Régimen de Operación
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: 'bold', my: 1.5, color: hasActiveLRSPP ? 'warning.main' : 'text.secondary', display: 'flex', alignItems: 'center', gap: 1 }}>
                  {hasActiveLRSPP ? (
                    <>
                      <CheckCircleIcon sx={{ color: 'warning.main' }} /> LRSPP ACTIVO
                    </>
                  ) : (
                    <>
                      <SpeedIcon sx={{ color: 'text.secondary' }} /> SPR CONVENCIONAL
                    </>
                  )}
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  {hasActiveLRSPP 
                    ? 'Bajas pérdidas óhmicas y propagación de rango largo.' 
                    : 'Modo convencional localizado por asimetría de la pila.'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Alerta de Resultados */}
      {data && (
        <Alert severity={hasActiveLRSPP ? "success" : "info"} sx={{ mb: 4 }}>
          <AlertTitle sx={{ fontWeight: 'bold' }}>Análisis de Ondas Superficiales</AlertTitle>
          {data.message}
        </Alert>
      )}

      {/* Gráfico de Barrido */}
      <Paper variant="outlined" sx={{ p: 3, mb: 4, bgcolor: '#fff' }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 3 }}>
          {sweepType === 'metal_thickness' 
            ? 'Longitud de Propagación (L_prop) vs. Espesor del Metal'
            : 'Longitud de Propagación (L_prop) vs. Índice de Refracción del Buffer'}
        </Typography>

        <Box sx={{ height: 350, width: '100%' }}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
              <CircularProgress />
            </Box>
          ) : chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis 
                  dataKey="value" 
                  type="number"
                  domain={['auto', 'auto']}
                  label={{ 
                    value: sweepType === 'metal_thickness' ? 'Espesor Metálico (nm)' : 'Índice de Refracción del Buffer (n)', 
                    position: 'insideBottom', 
                    offset: -10, 
                    fontSize: 12,
                    fontWeight: 'bold'
                  }} 
                />
                <YAxis 
                  yAxisId="left"
                  label={{ 
                    value: 'Longitud de Propagación L_prop (µm)', 
                    angle: -90, 
                    position: 'insideLeft', 
                    offset: 15,
                    fontSize: 12,
                    fontWeight: 'bold'
                  }} 
                />
                <YAxis 
                  yAxisId="right"
                  orientation="right"
                  label={{ 
                    value: 'Profundidad de Penetración L_pen (nm)', 
                    angle: 90, 
                    position: 'insideRight', 
                    offset: 15,
                    fontSize: 12,
                    fontWeight: 'bold'
                  }} 
                />
                <Tooltip 
                  formatter={(value: any, name: any) => {
                    if (name === "L_prop") return [`${Number(value).toFixed(2)} µm`, "Longitud de Propagación"] as any;
                    if (name === "L_pen") return [`${Number(value).toFixed(1)} nm`, "Profundidad de Penetración"] as any;
                    return [value, name] as any;
                  }}
                  labelFormatter={(label: any) => 
                    sweepType === 'metal_thickness' 
                      ? `Espesor: ${Number(label).toFixed(1)} nm` 
                      : `Índice de Refracción: ${Number(label).toFixed(4)}`
                  }
                />
                <Legend verticalAlign="top" height={36} />
                <Line 
                  yAxisId="left"
                  type="monotone" 
                  dataKey="L_prop" 
                  name="L_prop"
                  stroke="#2e7d32" 
                  strokeWidth={3} 
                  dot={{ r: 4 }}
                  activeDot={{ r: 7 }}
                />
                <Line 
                  yAxisId="right"
                  type="monotone" 
                  dataKey="L_pen" 
                  name="L_pen"
                  stroke="#9c27b0" 
                  strokeWidth={2} 
                  strokeDasharray="4 4"
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
              <Typography color="textSecondary">No hay datos de resonancia válidos en este rango. Configure la simulación con una capa metálica.</Typography>
            </Box>
          )}
        </Box>
      </Paper>

      {/* Tarjeta de Educación Física */}
      <Paper variant="outlined" sx={{ p: 3, bgcolor: '#fbfbfb', borderLeft: '5px solid #1976d2' }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 'bold', color: 'primary.main', mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <InfoIcon /> Fundamento de Física Óptica: LRSPP
        </Typography>
        
        <Typography variant="body2" color="text.primary" component="p" sx={{ mb: 2 }}>
          Cuando una película metálica extremadamente delgada está rodeada por ambos lados por dieléctricos de índice de refracción muy similar, los plasmones de superficie (SPP) de la interfaz superior y la inferior interactúan fuertemente.
        </Typography>

        <Typography variant="body2" color="text.primary" component="p" sx={{ mb: 2 }}>
          Esta interacción acopla las ondas y da lugar a dos modos propios súper-impuestos:
        </Typography>

        <Box sx={{ pl: 2, borderLeft: '3px solid #e0e0e0', mb: 2 }}>
          <Typography variant="body2" component="p" sx={{ mb: 2 }}>
            <strong>1. Modo Simétrico (LRSPP - Long-Range Surface Plasmon):</strong> La distribución del campo eléctrico transversal es simétrica, lo que empuja el campo electromagnético hacia afuera del metal, reduciendo drásticamente la disipación óhmica (pérdidas). Como resultado, la longitud de propagación lateral explota (pudiendo pasar de 10 µm a más de 500 µm) y la profundidad de penetración en el analito crece de forma ultra-profunda.
          </Typography>
          <Typography variant="body2" component="p">
            <strong>2. Modo Antisimétrico (SRSPP - Short-Range Surface Plasmon):</strong> La distribución del campo es antisimétrica, lo que concentra el campo dentro del metal delgado, incrementando enormemente la atenuación óhmica y reduciendo su longitud de propagación a fracciones de micrómetro.
          </Typography>
        </Box>

        <Typography variant="body2" sx={{ fontWeight: 'bold', mt: 2, color: 'text.secondary' }}>
          💡 Recomendaciones para Diseñadores:
        </Typography>
        <Typography variant="body2" component="ul" sx={{ pl: 3, mt: 1 }}>
          <li><strong>Grosor del Metal:</strong> Para activar LRSPP, reduzca el espesor del oro a 10 - 20 nm (el SPR estándar usa 50 nm).</li>
          <li><strong>Simetría de Índices:</strong> Introduzca una capa buffer gruesa (como Cytop, Teflón o un hidrogel con n ≈ 1.33 - 1.34) entre el prisma de acoplamiento y el metal delgado para equilibrar el índice del analito externo (agua n ≈ 1.333).</li>
          <li><strong>Monitoreo de FWHM:</strong> Notará la activación del LRSPP por la aparición de un dip de resonancia extremadamente afilado y angosto en la reflectancia.</li>
        </Typography>
      </Paper>
    </Box>
  );
};

export default LRSPPPanel;
