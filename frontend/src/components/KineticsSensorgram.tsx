import React, { useState } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Label
} from 'recharts';
import { Box, Button, TextField, Paper, Typography, Divider, Stack } from '@mui/material';

const KineticsSensorgram: React.FC = () => {
  const [ka, setKa] = useState(1e4); // M^-1 s^-1
  const [kd, setKd] = useState(1e-3); // s^-1
  const [conc, setConc] = useState(1e-6); // M (1 uM)
  const [tAssoc, setTAssoc] = useState(120); // s
  const [tTotal, setTTotal] = useState(300); // s
  const [maxShift, setMaxShift] = useState(0.5); // deg or nm
  const [simulatedData, setSimulatedData] = useState<any[] | null>(null);

  const runSimulation = () => {
    const data: any[] = [];
    const step = 1; // 1s intervals
    
    // Langmuir kinetics constants
    const eqGammaRatio = (ka * conc) / (ka * conc + kd);
    const rateAssoc = ka * conc + kd;
    
    // Value of Gamma/Gamma_max at end of association
    const gammaAtAssoc = eqGammaRatio * (1 - Math.exp(-rateAssoc * tAssoc));

    for (let t = 0; t <= tTotal; t += step) {
      let shift = 0;
      if (t <= tAssoc) {
        // Association phase
        const ratio = eqGammaRatio * (1 - Math.exp(-rateAssoc * t));
        shift = maxShift * ratio;
      } else {
        // Dissociation phase
        const ratio = gammaAtAssoc * Math.exp(-kd * (t - tAssoc));
        shift = maxShift * ratio;
      }
      
      data.push({
        time: t,
        shift: Number(shift.toFixed(5))
      });
    }
    
    setSimulatedData(data);
  };

  return (
    <Box>
      <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
        Configura los parámetros cinéticos de adsorción en superficie (modelo Langmuir 1:1) para generar el sensograma de la interacción ligando-analito.
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
          label="Desplazamiento Máx (deg/nm)"
          type="number"
          size="small"
          slotProps={{ htmlInput: { step: 0.1 } }}
          value={maxShift}
          onChange={(e) => setMaxShift(Number(e.target.value))}
        />
        
        <Button 
          variant="contained" 
          onClick={runSimulation}
          size="medium"
        >
          Simular Sensograma
        </Button>
      </Stack>

      <Divider sx={{ mb: 3 }} />

      {simulatedData && (
        <Box>
          <Box sx={{ mb: 2, p: 2, bgcolor: '#e8f5e9', borderRadius: 1, borderLeft: '5px solid #2e7d32' }}>
            <Typography variant="body2">
              <strong>Análisis Cinético:</strong> El gráfico muestra la señal en tiempo real. La fase de <strong>Asociación</strong> ocurre hasta los {tAssoc} s (flujo de analito), y la fase de <strong>Disociación</strong> (lavado con buffer) ocurre hasta los {tTotal} s.
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
                  domain={[0, maxShift * 1.1]} 
                  tick={{ fontSize: 12 }}
                >
                  <Label value="Desplazamiento de Resonancia (Δ)" angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} />
                </YAxis>
                <Tooltip 
                  formatter={(value: any) => `${Number(value).toFixed(4)}`}
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
                  <Label value="Lavado (Buffer)" position="top" fill="#ff1744" fontSize={10} />
                </ReferenceLine>
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Box>
      )}
    </Box>
  );
};

export default KineticsSensorgram;
