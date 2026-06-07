import React, { useState, useRef, useEffect } from 'react';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Label, ReferenceArea
} from 'recharts';
import { Box, Button, CircularProgress, TextField, Stack, Paper, Typography, Divider, ToggleButton, ToggleButtonGroup } from '@mui/material';
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
  const [viewMode, setViewMode] = useState<'1d' | '2d'>('1d');
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (viewMode !== '2d' || !data || !data.field_2d || !data.x_2d) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const field2D = data.field_2d;
    const zVals = data.z;
    const layerBounds = data.layer_bounds;
    const materials = data.materials;

    const Nz = field2D.length;
    const Nx = field2D[0].length;
    const canvasWidth = canvas.width;
    const canvasHeight = canvas.height;

    // Find min and max of the field for color scaling
    let minVal = Infinity;
    let maxVal = -Infinity;
    for (let i = 0; i < Nz; i++) {
      for (let j = 0; j < Nx; j++) {
        const val = field2D[i][j];
        if (val < minVal) minVal = val;
        if (val > maxVal) maxVal = val;
      }
    }

    const range = maxVal - minVal || 1;

    // Create an image data buffer for fast rendering
    const imgData = ctx.createImageData(Nx, Nz);
    for (let zIdx = 0; zIdx < Nz; zIdx++) {
      const y = Nz - 1 - zIdx; // Invert vertically (Prism at bottom)
      for (let xIdx = 0; xIdx < Nx; xIdx++) {
        const val = field2D[zIdx][xIdx];
        const norm = (val - minVal) / range;
        
        let r = 0, g = 0, b = 0;
        // Premium Plasma color scheme
        if (norm < 0.5) {
          const t = norm * 2;
          r = Math.floor(13 + (240 - 13) * t);
          g = Math.floor(8 + (80 - 8) * t);
          b = Math.floor(135 + (138 - 135) * t);
        } else {
          const t = (norm - 0.5) * 2;
          r = Math.floor(240 + (254 - 240) * t);
          g = Math.floor(80 + (224 - 80) * t);
          b = Math.floor(138 + (139 - 138) * t);
        }

        const pixelIdx = (y * Nx + xIdx) * 4;
        imgData.data[pixelIdx] = r;
        imgData.data[pixelIdx + 1] = g;
        imgData.data[pixelIdx + 2] = b;
        imgData.data[pixelIdx + 3] = 255;
      }
    }

    // Scale to main canvas
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = Nx;
    tempCanvas.height = Nz;
    const tempCtx = tempCanvas.getContext('2d');
    if (tempCtx) {
      tempCtx.putImageData(imgData, 0, 0);
      ctx.imageSmoothingEnabled = true;
      ctx.clearRect(0, 0, canvasWidth, canvasHeight);
      ctx.drawImage(tempCanvas, 0, 0, canvasWidth, canvasHeight);
    }

    // Overlay layer boundaries
    const zMin = zVals[0];
    const zMax = zVals[Nz - 1];
    const zRange = zMax - zMin;

    layerBounds.forEach((bound, idx) => {
      const y = canvasHeight * (1 - (bound - zMin) / zRange);
      
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
      ctx.setLineDash([5, 5]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvasWidth, y);
      ctx.stroke();

      // Text label
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 11px Inter, Roboto, sans-serif';
      ctx.shadowColor = 'rgba(0,0,0,0.8)';
      ctx.shadowBlur = 4;
      ctx.fillText(materials[idx + 1] || "", 15, y - 6);
      ctx.shadowBlur = 0;
    });

    // Substrate and Superstrate labels
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 11px Inter, Roboto, sans-serif';
    ctx.shadowColor = 'rgba(0,0,0,0.8)';
    ctx.shadowBlur = 4;
    ctx.fillText(`${materials[0]} (Sustrato)`, 15, canvasHeight - 15);
    ctx.fillText(`${materials[materials.length - 1]} (Superstrato)`, 15, 25);
    ctx.shadowBlur = 0;

  }, [viewMode, data]);

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
            <Stack direction="row" sx={{ mb: 2, justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="body2" color="textSecondary" sx={{ fontWeight: 'bold' }}>
                Distribución del Campo Eléctrico Normalizado @ {theta}°
              </Typography>
              <ToggleButtonGroup
                value={viewMode}
                exclusive
                onChange={(_, mode) => { if (mode !== null) setViewMode(mode); }}
                size="small"
                color="primary"
              >
                <ToggleButton value="1d" sx={{ textTransform: 'none', fontWeight: 'bold' }}>Perfil 1D (|E|²)</ToggleButton>
                <ToggleButton value="2d" sx={{ textTransform: 'none', fontWeight: 'bold' }}>Mapa de Campo 2D (Frentes de Onda)</ToggleButton>
              </ToggleButtonGroup>
            </Stack>

            <Paper variant="outlined" sx={{ height: 450, p: 2, bgcolor: '#fff', position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              {viewMode === '1d' ? (
                <>
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
                </>
              ) : (
                data.field_2d && data.x_2d ? (
                  <Box sx={{ width: '100%', height: '100%', position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                    <canvas 
                      ref={canvasRef} 
                      width={650} 
                      height={380} 
                      style={{ maxWidth: '100%', maxHeight: '100%', border: '1px solid #e0e0e0', borderRadius: 4, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}
                    />
                    <Box sx={{ mt: 1.5, display: 'flex', justifyContent: 'center', gap: 3 }}>
                      <Typography variant="caption" sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: '#0d0887', borderRadius: 2 }} /> Campo Mínimo (-)
                      </Typography>
                      <Typography variant="caption" sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: '#f0508a', borderRadius: 2 }} /> Cero
                      </Typography>
                      <Typography variant="caption" sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: '#febb2b', borderRadius: 2 }} /> Campo Máximo (+)
                      </Typography>
                    </Box>
                  </Box>
                ) : (
                  <Typography variant="body2" color="textSecondary">
                    Mapa de campo 2D no disponible para esta configuración.
                  </Typography>
                )
              )}
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
