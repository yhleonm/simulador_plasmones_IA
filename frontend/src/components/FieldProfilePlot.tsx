import React, { useState } from 'react';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Label, ReferenceArea
} from 'recharts';
import { Box, Button, CircularProgress, TextField, Stack, Paper, Typography, Divider } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
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

  const exportToCSV = () => {
    if (!data) return;
    
    let metadata = "# SIMULADOR SPR-LMR - METADATOS DE PERFIL DE CAMPO\n";
    metadata += `# Longitud de Onda: ${wavelength} nm\n`;
    metadata += `# Polarizacion: ${polarization}\n`;
    metadata += `# Angulo de Incidencia: ${theta}°\n`;
    if (data.penetration_depth !== undefined && data.penetration_depth !== null) {
      metadata += `# Profundidad de penetracion analitica (L): ${data.penetration_depth.toFixed(4)} nm\n`;
    }
    if (data.enhancement_factor !== undefined && data.enhancement_factor !== null) {
      metadata += `# Factor de realce de campo max (EF): ${data.enhancement_factor.toFixed(4)}x\n`;
    }
    if (data.propagation_length !== undefined && data.propagation_length !== null) {
      metadata += `# Longitud de propagacion del plasmon (Le): ${data.propagation_length.toFixed(4)} nm\n`;
    }
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
    
    let csvContent = metadata + "Posicion z (nm),Intensidad |E|²\n";
    data.z.forEach((zVal, i) => {
      csvContent += `${zVal.toFixed(4)},${data.E_sq[i].toFixed(6)}\n`;
    });
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `perfil_campo_spr_${theta}deg.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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
                  <defs>
                    <linearGradient id="evanescentGrad" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#9c27b0" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#9c27b0" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
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
                  {lastBoundary !== undefined && chartData.length > 0 && (
                    <ReferenceArea 
                      x1={lastBoundary} 
                      x2={chartData[chartData.length - 1]?.z} 
                      fill="url(#evanescentGrad)" 
                      ifOverflow="visible"
                    />
                  )}
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

            <Box sx={{ mt: 3, mb: 2 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 2, color: 'text.primary', letterSpacing: 0.5 }}>
                Métricas Físicas Avanzadas del Sensor
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
                {data.penetration_depth !== undefined && data.penetration_depth !== null && (
                  <Paper variant="outlined" sx={{ p: 2, borderLeft: '5px solid #9c27b0', bgcolor: '#fbf7fc' }}>
                    <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold', display: 'block' }}>
                      PROFUNDIDAD DE PENETRACIÓN ANALÍTICA (L)
                    </Typography>
                    <Typography variant="h5" color="secondary" sx={{ fontWeight: 'bold', my: 1 }}>
                      {data.penetration_depth.toFixed(1)} nm
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      Distancia teórica a la cual la <strong>amplitud del campo eléctrico</strong> decae a 1/e (36.8%) de su valor en la interfaz. Clave para evaluar el acoplamiento con analitos voluminosos como proteínas o virus.
                    </Typography>
                  </Paper>
                )}
                {lp !== null && (
                  <Paper variant="outlined" sx={{ p: 2, borderLeft: '5px solid #1976d2', bgcolor: '#f5f9ff' }}>
                    <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold', display: 'block' }}>
                      PROFUNDIDAD DE DECAIMIENTO DE INTENSIDAD (Lp)
                    </Typography>
                    <Typography variant="h5" color="primary" sx={{ fontWeight: 'bold', my: 1 }}>
                      {lp.toFixed(1)} nm
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      Distancia calculada donde la <strong>intensidad del campo (|E|²)</strong> se reduce a 1/e (36.8%). En un medio dieléctrico transparente, equivale exactamente a la mitad de L (L/2 = {(data.penetration_depth ? (data.penetration_depth / 2) : (lp)).toFixed(1)} nm).
                    </Typography>
                  </Paper>
                )}
                {data.enhancement_factor !== undefined && data.enhancement_factor !== null && (
                  <Paper variant="outlined" sx={{ p: 2, borderLeft: '5px solid #2e7d32', bgcolor: '#f1f8e9' }}>
                    <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold', display: 'block' }}>
                      FACTOR DE REALCE DEL CAMPO (EF)
                    </Typography>
                    <Typography variant="h5" sx={{ color: 'success.main', fontWeight: 'bold', my: 1 }}>
                      {data.enhancement_factor.toFixed(1)}x
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      Amplificación máxima de la <strong>intensidad local (|E|²/|E₀|²)</strong>. Un factor elevado indica un fuerte acoplamiento plasmónico y alta sensibilidad de transducción.
                    </Typography>
                  </Paper>
                )}
                {data.propagation_length !== undefined && data.propagation_length !== null && (
                  <Paper variant="outlined" sx={{ p: 2, borderLeft: '5px solid #ed6c02', bgcolor: '#fffde7' }}>
                    <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold', display: 'block' }}>
                      LONGITUD DE PROPAGACIÓN DEL PLASMÓN (Le)
                    </Typography>
                    <Typography variant="h5" sx={{ color: 'warning.main', fontWeight: 'bold', my: 1 }}>
                      {(data.propagation_length / 1000).toFixed(2)} µm <Typography component="span" variant="body2" color="textSecondary">({data.propagation_length.toFixed(0)} nm)</Typography>
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      Distancia en el plano de la interfaz sobre la cual el plasmón viaja antes de disiparse. Determina la <strong>resolución espacial y el grado de deslocalización</strong> lateral del sensor.
                    </Typography>
                  </Paper>
                )}
              </Box>
            </Box>

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
