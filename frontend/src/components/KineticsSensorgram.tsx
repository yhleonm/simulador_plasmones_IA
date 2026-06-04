import React, { useState } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Label
} from 'recharts';
import { Box, Button, TextField, Paper, Typography, Divider, Stack, CircularProgress } from '@mui/material';
import type { LayerConfig } from '../types';
import { simulateKinetics } from '../api/client';

interface Props {
  layers: LayerConfig[];
  wavelength: number;
  polarization: 'TM' | 'TE';
  interrogationMode: 'angular' | 'spectral';
  fixedAngle: number;
}

const KineticsSensorgram: React.FC<Props> = ({
  layers,
  wavelength,
  polarization,
  interrogationMode,
  fixedAngle
}) => {
  const [ka, setKa] = useState(1e4); // M^-1 s^-1
  const [kd, setKd] = useState(1e-3); // s^-1
  const [conc, setConc] = useState(1e-6); // M (1 uM)
  const [tAssoc, setTAssoc] = useState(120); // s
  const [tTotal, setTTotal] = useState(300); // s
  const [dMax, setDMax] = useState(5.0); // nm (Max thickness of adlayer)
  const [nAdlayer, setNAdlayer] = useState(1.45); // Refractive index of biological adlayer

  const [loading, setLoading] = useState(false);
  const [simulatedData, setSimulatedData] = useState<any[] | null>(null);
  const [unit, setUnit] = useState<'deg' | 'nm'>('deg');

  const runSimulation = async () => {
    setLoading(true);
    try {
      const response = await simulateKinetics({
        layers,
        wavelength_nm: wavelength,
        polarization,
        interrogation_mode: interrogationMode,
        fixed_angle_deg: fixedAngle,
        ka,
        kd,
        concentration: conc,
        t_assoc: tAssoc,
        t_total: tTotal,
        d_max: dMax,
        n_adlayer: nAdlayer
      });
      
      setSimulatedData(response.points);
      setUnit(response.unit as 'deg' | 'nm');
    } catch (err) {
      console.error("Kinetics simulation failed:", err);
      alert("Error al simular la cinética física TMM.");
    } finally {
      setLoading(false);
    }
  };

  const getUnitString = () => {
    return unit === 'nm' ? 'nm' : 'grados (°)';
  };

  const getAxisLabel = () => {
    return unit === 'nm' 
      ? 'Desplazamiento de longitud de onda (Δλ, nm)' 
      : 'Desplazamiento de ángulo de resonancia (Δθ, °)';
  };

  return (
    <Box>
      <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
        Simulación física completa conectando cinética química de adsorción (Langmuir 1:1) con el motor óptico TMM.
        Se asume que el ligando se une en la superficie creando una capa biomolecular que crece en espesor (hasta un máximo de <strong>d_max</strong>) con un índice de refracción <strong>n_adlayer</strong>.
      </Typography>
      
      <Stack direction="row" spacing={2} sx={{ mb: 3, flexWrap: 'wrap', gap: 2 }}>
        <TextField
          label="Const. Asociación ka (M⁻¹s⁻¹)"
          type="number"
          size="small"
          slotProps={{ htmlInput: { step: 1000 } }}
          value={ka}
          onChange={(e) => setKa(Number(e.target.value))}
        />
        <TextField
          label="Const. Disociación kd (s⁻¹)"
          type="number"
          size="small"
          slotProps={{ htmlInput: { step: 0.0001 } }}
          value={kd}
          onChange={(e) => setKd(Number(e.target.value))}
        />
        <TextField
          label="Concentración Analito C (M)"
          type="number"
          size="small"
          slotProps={{ htmlInput: { step: 1e-7 } }}
          value={conc}
          onChange={(e) => setConc(Number(e.target.value))}
        />
        <TextField
          label="Tiempo de Inyección (s)"
          type="number"
          size="small"
          value={tAssoc}
          onChange={(e) => setTAssoc(Number(e.target.value))}
        />
        <TextField
          label="Tiempo Total (s)"
          type="number"
          size="small"
          value={tTotal}
          onChange={(e) => setTTotal(Number(e.target.value))}
        />
        <TextField
          label="Espesor Máx Adcapa d_max (nm)"
          type="number"
          size="small"
          slotProps={{ htmlInput: { step: 0.5 } }}
          value={dMax}
          onChange={(e) => setDMax(Number(e.target.value))}
        />
        <TextField
          label="Índice Adcapa n_adlayer"
          type="number"
          size="small"
          slotProps={{ htmlInput: { step: 0.01 } }}
          value={nAdlayer}
          onChange={(e) => setNAdlayer(Number(e.target.value))}
        />
        
        <Button 
          variant="contained" 
          onClick={runSimulation}
          size="medium"
          disabled={loading || layers.length === 0}
          startIcon={loading ? <CircularProgress size={20} color="inherit" /> : null}
        >
          {loading ? 'Calculando TMM...' : 'Simular Sensograma'}
        </Button>
      </Stack>

      <Divider sx={{ mb: 3 }} />

      {simulatedData && !loading && (
        <Box>
          <Box sx={{ mb: 2, p: 2, bgcolor: '#e8f5e9', borderRadius: 1, borderLeft: '5px solid #2e7d32' }}>
            <Typography variant="body2">
              <strong>Análisis Cinético-Óptico:</strong> El sensograma calcula el corrimiento real de la resonancia para cada instante.
              Ante una saturación molecular con un espesor acumulativo de <strong>{dMax} nm</strong> y refracción de <strong>{nAdlayer}</strong>, el corrimiento máximo obtenido es de <strong>{simulatedData[simulatedData.length - 1]?.shift.toFixed(4)} {getUnitString()}</strong>.
            </Typography>
          </Box>
          <Paper variant="outlined" sx={{ height: 400, p: 2, bgcolor: '#fff' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={simulatedData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis 
                  dataKey="time" 
                  type="number" 
                  domain={[0, tTotal]}
                  tick={{ fontSize: 12 }}
                >
                  <Label value="Tiempo (s)" offset={-10} position="insideBottom" />
                </XAxis>
                <YAxis 
                  tick={{ fontSize: 12 }}
                >
                  <Label 
                    value={getAxisLabel()} 
                    angle={-90} 
                    position="insideLeft" 
                    style={{ textAnchor: 'middle' }} 
                  />
                </YAxis>
                <Tooltip 
                  formatter={(value: any) => [`${Number(value).toFixed(4)} ${unit}`, 'Desplazamiento (Δ)']}
                  labelFormatter={(label: any) => `Tiempo: ${label} s`}
                />
                <Line 
                  type="monotone" 
                  dataKey="shift" 
                  name="Señal del Sensorgrama"
                  stroke="#2e7d32" 
                  strokeWidth={3} 
                  dot={false} 
                  isAnimationActive={false}
                />
                <ReferenceLine x={tAssoc} stroke="#ff1744" strokeDasharray="3 3">
                  <Label value="Inyección de Buffer (Lavado)" position="top" fill="#ff1744" fontSize={11} />
                </ReferenceLine>
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Box>
      )}

      {loading && (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 300 }}>
          <CircularProgress size={50} sx={{ mb: 2 }} />
          <Typography variant="body2" color="textSecondary">
            Simulando cinética de adsorción y resolviendo ecuaciones TMM para cada punto temporal...
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default KineticsSensorgram;
