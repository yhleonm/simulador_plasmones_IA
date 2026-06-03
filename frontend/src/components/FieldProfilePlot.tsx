import React, { useState } from 'react';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Label
} from 'recharts';
import { Box, Button, CircularProgress, TextField, Stack, Paper, Typography, Divider } from '@mui/material';
import { simulateFieldProfile } from '../api/client';
import type { LayerConfig, FieldProfileResponse } from '../types';

interface Props {
  layers: LayerConfig[];
  wavelength: number;
  polarization: 'TM' | 'TE';
}

const FieldProfilePlot: React.FC<Props> = ({ layers, wavelength, polarization }) => {
  const [data, setData] = useState<FieldProfileResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [theta, setTheta] = useState(44.0);

  const handleSimulate = async () => {
    setLoading(true);
    try {
      const result = await simulateFieldProfile({
        wavelength_nm: wavelength,
        polarization,
        layers,
        theta_deg: theta
      });
      setData(result);
    } catch (error: any) {
      console.error("Field simulation failed", error);
      alert("Error en la simulación de campo: " + (error.message || "Error desconocido"));
    }
    setLoading(false);
  };

  const chartData = data ? data.z.map((z, i) => ({
    z: z,
    Esq: data.E_sq[i]
  })) : [];

  return (
    <Box>
      <Stack direction="row" spacing={2} sx={{ mb: 2, alignItems: 'center' }}>
        <TextField
          label="Ángulo de Incidencia (°)"
          type="number"
          size="small"
          sx={{ width: 180 }}
          value={theta}
          onChange={(e) => setTheta(Number(e.target.value))}
        />
        <Button 
          variant="contained" 
          onClick={handleSimulate} 
          disabled={loading}
        >
          {loading ? <CircularProgress size={24} /> : 'Generar Perfil de Campo'}
        </Button>
      </Stack>
      <Divider sx={{ mb: 2 }} />

      {data && (() => {
        // Evanescent penetration depth calculation
        let lp: number | null = null;
        let lastBoundary = 0;
        if (data && data.layer_bounds.length > 0) {
          lastBoundary = data.layer_bounds[data.layer_bounds.length - 1];
          const boundaryIdx = data.z.findIndex(val => val >= lastBoundary);
          if (boundaryIdx !== -1) {
            const I0 = data.E_sq[boundaryIdx];
            const targetVal = I0 * Math.exp(-1);
            const decayIdx = data.z.findIndex((_, idx) => idx > boundaryIdx && data.E_sq[idx] <= targetVal);
            if (decayIdx !== -1) {
              lp = data.z[decayIdx] - lastBoundary;
            }
          }
        }

        return (
          <Box>
            <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
              Intensidad del Campo Eléctrico Normalizado (|E|²) @ {theta}°
            </Typography>
            <Paper variant="outlined" sx={{ height: 450, p: 2, bgcolor: '#fff', position: 'relative' }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 20, bottom: 25 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis 
                    dataKey="z" 
                    type="number" 
                    domain={['auto', 'auto']}
                    tick={{ fontSize: 11 }}
                  >
                    <Label value="Posición z (nm)" offset={-15} position="insideBottom" />
                  </XAxis>
                  <YAxis tick={{ fontSize: 11 }}>
                    <Label value="Intensidad |E|²" angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} />
                  </YAxis>
                  <Tooltip 
                    formatter={(value: any) => Number(value).toFixed(4)}
                    labelFormatter={(label: any) => `z: ${Number(label).toFixed(1)} nm`}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="Esq" 
                    name="|E|²"
                    stroke="#1976d2" 
                    fill="#bbdefb"
                    fillOpacity={0.6}
                    strokeWidth={2} 
                    isAnimationActive={false}
                  />
                  {data.layer_bounds.map((bound, idx) => (
                    <ReferenceLine 
                      key={idx} 
                      x={bound} 
                      stroke="#555" 
                      strokeWidth={1.5}
                      strokeDasharray="4 4"
                    >
                      <Label 
                        value={data.materials[idx+1] || ""} 
                        position="insideTopRight" 
                        fill="#555" 
                        fontSize={10}
                        angle={-90}
                        offset={10}
                      />
                    </ReferenceLine>
                  ))}
                  {lp !== null && (
                    <ReferenceLine x={lastBoundary + lp} stroke="#9c27b0" strokeWidth={1.5} strokeDasharray="3 3">
                      <Label value={`L_p = ${lp.toFixed(1)} nm`} position="top" fill="#9c27b0" fontSize={10} />
                    </ReferenceLine>
                  )}
                </AreaChart>
              </ResponsiveContainer>
              
              {/* Etiquetas de las regiones semi-infinitas */}
              <Typography 
                variant="caption" 
                sx={{ position: 'absolute', left: 50, top: 40, color: 'text.secondary', fontWeight: 'bold' }}
              >
                {data.materials[0]} (Sustrato)
              </Typography>
              <Typography 
                variant="caption" 
                sx={{ position: 'absolute', right: 50, top: 40, color: 'text.secondary', fontWeight: 'bold' }}
              >
                {data.materials[data.materials.length - 1]} (Superstrato)
              </Typography>
            </Paper>

            {lp !== null && (
              <Box sx={{ mt: 2, p: 2, bgcolor: '#f3e5f5', borderRadius: 1, borderLeft: '5px solid #9c27b0', mb: 2 }}>
                <Typography variant="body2">
                  <strong>Profundidad de Penetración Evanescente (L_p):</strong> {lp.toFixed(1)} nm. 
                  Esta es la distancia en la cual la intensidad del campo disminuye a 1/e (36.8%) de su valor superficial en el medio de detección. Define el rango efectivo del sensor para detectar analitos y biomoléculas.
                </Typography>
              </Box>
            )}

            <Box sx={{ mt: 2, p: 2, bgcolor: '#e3f2fd', borderRadius: 1 }}>
              <Typography variant="caption" sx={{ display: 'block' }}>
                <strong>Nota Física:</strong> En resonancia, deberías observar un máximo de intensidad en la interfaz metal/dieléctrico y un decaimiento exponencial hacia el superstrato (campo evanescente).
              </Typography>
            </Box>
          </Box>
        );
      })()}
    </Box>
  );
};

export default FieldProfilePlot;
