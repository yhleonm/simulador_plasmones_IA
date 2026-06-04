import React, { useState, useRef, useEffect } from 'react';
import { 
  Box, Button, TextField, Typography, Paper, Stack, CircularProgress, Grid, 
  Card, CardContent, Divider, MenuItem
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import type { LayerConfig } from '../types';
import { simulateReflectance2D } from '../api/client';
import type { Simulation2DResponse } from '../types';

interface Props {
  layers: LayerConfig[];
  polarization: 'TM' | 'TE';
}

const getViridisColor = (r: number): string => {
  const v = Math.max(0, Math.min(1, r));
  // Scientific Viridis colormap control stops
  const stops = [
    { x: 0.0, r: 68, g: 1, b: 84 },     // Dark purple
    { x: 0.25, r: 59, g: 82, b: 139 },  // Blue
    { x: 0.5, r: 33, g: 145, b: 140 },  // Teal
    { x: 0.75, r: 94, g: 201, b: 98 },  // Green
    { x: 1.0, r: 253, g: 231, b: 37 }   // Yellow
  ];

  for (let i = 0; i < stops.length - 1; i++) {
    const s1 = stops[i];
    const s2 = stops[i+1];
    if (v >= s1.x && v <= s2.x) {
      const ratio = (v - s1.x) / (s2.x - s1.x);
      const rColor = Math.round(s1.r + (s2.r - s1.r) * ratio);
      const gColor = Math.round(s1.g + (s2.g - s1.g) * ratio);
      const bColor = Math.round(s1.b + (s2.b - s1.b) * ratio);
      return `rgb(${rColor}, ${gColor}, ${bColor})`;
    }
  }
  return `rgb(253, 231, 37)`;
};

const Reflectance2DMap: React.FC<Props> = ({ layers, polarization }) => {
  const [angleMin, setAngleMin] = useState(35.0);
  const [angleMax, setAngleMax] = useState(80.0);
  const [wlMin, setWlMin] = useState(450.0);
  const [wlMax, setWlMax] = useState(850.0);
  const [steps, setSteps] = useState(80); // 80x80 mesh = 6,400 calculations
  
  const [loading, setLoading] = useState(false);
  const [mapData, setMapData] = useState<Simulation2DResponse | null>(null);
  
  // Interactive Hover states
  const [hoverInfo, setHoverInfo] = useState<{
    x: number;
    y: number;
    angle: number;
    wavelength: number;
    reflectance: number;
  } | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const handleSimulate = async () => {
    setLoading(true);
    setMapData(null);
    setHoverInfo(null);
    try {
      const result = await simulateReflectance2D({
        layers,
        polarization,
        angle_min: angleMin,
        angle_max: angleMax,
        angle_steps: steps,
        wl_min: wlMin,
        wl_max: wlMax,
        wl_steps: steps
      });
      setMapData(result);
    } catch (err) {
      console.error("2D simulation failed", err);
      alert("Error calculando el mapa 2D.");
    } finally {
      setLoading(false);
    }
  };

  // Render Heatmap to HTML5 Canvas
  useEffect(() => {
    if (!mapData || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    const W = mapData.wavelengths.length; // Rows
    const A = mapData.angles.length;      // Columns

    const cellWidth = width / A;
    const cellHeight = height / W;

    // Draw grid of cells
    for (let r = 0; r < W; r++) {
      for (let c = 0; c < A; c++) {
        const val = mapData.matrix[r][c];
        const color = getViridisColor(val);
        
        // Calculate coords (y goes from top to bottom, so we reverse it to have wavelength increase going up)
        const x = c * cellWidth;
        const y = height - (r + 1) * cellHeight;

        ctx.fillStyle = color;
        // Drawing slightly overlapping rects (+0.5) to avoid gaps
        ctx.fillRect(x, y, cellWidth + 0.5, cellHeight + 0.5);
      }
    }
  }, [mapData]);

  // Handle Hover Tooltip calculation
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!mapData || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();

    // Mouse coordinates relative to canvas bounding box
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const W = mapData.wavelengths.length;
    const A = mapData.angles.length;

    // Normalized index mapping
    const c = Math.floor((x / rect.width) * A);
    // Remember y is flipped in the rendering loop
    const r = Math.floor(((rect.height - y) / rect.height) * W);

    if (r >= 0 && r < W && c >= 0 && c < A) {
      const angle = mapData.angles[c];
      const wl = mapData.wavelengths[r];
      const val = mapData.matrix[r][c];

      setHoverInfo({
        x: e.clientX - rect.left + 15,
        y: e.clientY - rect.top + 15,
        angle,
        wavelength: wl,
        reflectance: val
      });
    } else {
      setHoverInfo(null);
    }
  };

  const handleMouseLeave = () => {
    setHoverInfo(null);
  };

  return (
    <Box sx={{ mt: 1 }}>
      <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
        Genera un mapa bidimensional de reflectancia barriendo simultáneamente el ángulo de incidencia ($\theta$) y la longitud de onda de excitación ($\lambda$). El acoplamiento plasmónico o LMR se visualiza como una banda oscura.
      </Typography>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card variant="outlined" sx={{ p: 2, height: '100%' }}>
            <CardContent sx={{ p: 0 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 2 }}>Rangos de Escaneo</Typography>
              <Stack spacing={2}>
                <Stack direction="row" spacing={2}>
                  <TextField
                    label="Ángulo Mín (°)"
                    type="number"
                    size="small"
                    value={angleMin}
                    onChange={(e) => setAngleMin(Number(e.target.value))}
                  />
                  <TextField
                    label="Ángulo Máx (°)"
                    type="number"
                    size="small"
                    value={angleMax}
                    onChange={(e) => setAngleMax(Number(e.target.value))}
                  />
                </Stack>

                <Stack direction="row" spacing={2}>
                  <TextField
                    label="λ Mín (nm)"
                    type="number"
                    size="small"
                    value={wlMin}
                    onChange={(e) => setWlMin(Number(e.target.value))}
                  />
                  <TextField
                    label="λ Máx (nm)"
                    type="number"
                    size="small"
                    value={wlMax}
                    onChange={(e) => setWlMax(Number(e.target.value))}
                  />
                </Stack>

                <TextField
                  select
                  label="Resolución (Malla)"
                  size="small"
                  value={steps}
                  onChange={(e) => setSteps(Number(e.target.value))}
                >
                  <MenuItem value={50}>Rápido (50 x 50)</MenuItem>
                  <MenuItem value={80}>Estándar (80 x 80)</MenuItem>
                  <MenuItem value={120}>Alta (120 x 120)</MenuItem>
                </TextField>

                <Button
                  variant="contained"
                  color="primary"
                  startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <PlayArrowIcon />}
                  onClick={handleSimulate}
                  disabled={loading || layers.length === 0}
                  fullWidth
                  sx={{ py: 1.2 }}
                >
                  {loading ? 'Calculando Malla...' : 'Generar Mapa 2D'}
                </Button>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 8 }}>
          <Paper variant="outlined" sx={{ p: 2, display: 'flex', flexDirection: 'column', alignItems: 'center', bgcolor: '#fafafa', position: 'relative' }}>
            {loading && (
              <Box sx={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: 'rgba(255,255,255,0.7)', zIndex: 10 }}>
                <Stack spacing={2} sx={{ alignItems: 'center' }}>
                  <CircularProgress size={45} />
                  <Typography variant="body2" sx={{ fontWeight: 'bold' }}>Calculando malla electromagnética TMM...</Typography>
                </Stack>
              </Box>
            )}

            {!mapData && !loading && (
              <Box sx={{ height: 350, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Typography color="textSecondary" variant="body2">Configura los límites y haz clic en "Generar Mapa 2D" para visualizar la dispersión.</Typography>
              </Box>
            )}

            {mapData && (
              <Box sx={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <Box sx={{ position: 'relative', width: 550, height: 300, border: '1px solid #e0e0e0', cursor: 'crosshair', mb: 2 }}>
                  
                  {/* Y Axis Label (Vertical Left) */}
                  <Box sx={{ position: 'absolute', left: -40, top: '50%', transform: 'rotate(-90deg) translate(-50%, 0)', transformOrigin: 'left center', width: 200, textAlign: 'center' }}>
                    <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary' }}>Longitud de onda (nm)</Typography>
                  </Box>

                  {/* Canvas Plot */}
                  <canvas 
                    ref={canvasRef} 
                    width={550} 
                    height={300}
                    onMouseMove={handleMouseMove}
                    onMouseLeave={handleMouseLeave}
                    style={{ display: 'block', backgroundColor: '#440154' }}
                  />

                  {/* Interactive Tooltip inside plot container */}
                  {hoverInfo && (
                    <Box sx={{ 
                      position: 'absolute', 
                      left: hoverInfo.x, 
                      top: hoverInfo.y, 
                      bgcolor: 'rgba(0,0,0,0.85)', 
                      color: '#fff', 
                      p: 1, 
                      borderRadius: 1, 
                      pointerEvents: 'none', 
                      zIndex: 100,
                      boxShadow: 3
                    }}>
                      <Typography variant="caption" sx={{ display: 'block' }}><strong>Ángulo:</strong> {hoverInfo.angle.toFixed(2)}°</Typography>
                      <Typography variant="caption" sx={{ display: 'block' }}><strong>λ:</strong> {hoverInfo.wavelength.toFixed(1)} nm</Typography>
                      <Typography variant="caption" sx={{ display: 'block' }}><strong>R:</strong> {hoverInfo.reflectance.toFixed(4)}</Typography>
                    </Box>
                  )}
                </Box>

                {/* X Axis Label */}
                <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary', mb: 2 }}>
                  Ángulo de incidencia (deg)
                </Typography>

                {/* Legend or Scale Info */}
                <Divider sx={{ width: '100%', mb: 1.5 }} />
                <Stack direction="row" spacing={3} sx={{ width: '100%', justifyContent: 'space-between', px: 1 }}>
                  <Typography variant="caption" color="textSecondary">
                    Eje X: <strong>{angleMin}° a {angleMax}°</strong>
                  </Typography>
                  <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                    <Typography variant="caption" color="textSecondary">Escala (Viridis):</Typography>
                    <Box sx={{ 
                      width: 120, 
                      height: 12, 
                      borderRadius: 0.5, 
                      background: 'linear-gradient(to right, rgb(68,1,84), rgb(59,82,139), rgb(33,145,140), rgb(94,201,98), rgb(253,231,37))' 
                    }} />
                    <Stack direction="row" spacing={6} sx={{ position: 'relative', width: 120, mt: -0.5 }}>
                      <Typography variant="caption" sx={{ fontSize: 9, color: 'text.secondary', position: 'absolute', left: 0 }}>R=0</Typography>
                      <Typography variant="caption" sx={{ fontSize: 9, color: 'text.secondary', position: 'absolute', right: 0 }}>R=1</Typography>
                    </Stack>
                  </Stack>
                  <Typography variant="caption" color="textSecondary">
                    Eje Y: <strong>{wlMin} nm a {wlMax} nm</strong>
                  </Typography>
                </Stack>
              </Box>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Reflectance2DMap;
