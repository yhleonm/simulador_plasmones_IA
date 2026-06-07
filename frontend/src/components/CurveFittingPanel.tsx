import React, { useState, useEffect } from 'react';
import { 
  Box, Button, CircularProgress, TextField, Stack, Paper, Typography, 
  MenuItem, IconButton, Table, TableBody, TableCell, 
  TableContainer, TableHead, TableRow, Alert, Card, Grid 
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, 
  Legend, ResponsiveContainer, Label 
} from 'recharts';
import { fitCurve } from '../api/client';
import type { LayerConfig, FitParameterConfig, CurveFitResponse } from '../types';

interface Props {
  layers: LayerConfig[];
  setLayers: React.Dispatch<React.SetStateAction<LayerConfig[]>>;
  wavelength: number;
  polarization: 'TM' | 'TE';
  interrogationMode: 'angular' | 'spectral';
  fixedAngle: number;
}

interface ActiveParam {
  id: string;
  layerIndex: number;
  parameter: 'd' | 'n' | 'k';
  guess: number;
  minVal: number;
  maxVal: number;
}

const CurveFittingPanel: React.FC<Props> = ({ 
  layers, setLayers, wavelength, polarization, interrogationMode, fixedAngle 
}) => {
  const [xExp, setXExp] = useState<number[]>([]);
  const [yExp, setYExp] = useState<number[]>([]);
  const [fileName, setFileName] = useState<string>('');
  const [params, setParams] = useState<ActiveParam[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CurveFitResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Initialize with a default parameter if not present (usually the metal layer thickness)
  useEffect(() => {
    if (params.length === 0 && layers.length > 2) {
      // Find the first layer that has a thickness > 0 (typically layer 1 - metal)
      const metalIdx = layers.findIndex((l, idx) => idx > 0 && idx < layers.length - 1 && l.d > 0);
      const targetIdx = metalIdx !== -1 ? metalIdx : 1;
      const dVal = layers[targetIdx]?.d || 50;
      
      setParams([
        {
          id: Math.random().toString(36).substring(2, 9),
          layerIndex: targetIdx,
          parameter: 'd',
          guess: dVal,
          minVal: Math.max(0, dVal - 20),
          maxVal: dVal + 20
        }
      ]);
    }
  }, [layers]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      const lines = text.split(/\r?\n/);
      const parsedX: number[] = [];
      const parsedY: number[] = [];

      for (let line of lines) {
        line = line.trim();
        if (!line || line.startsWith('#') || line.startsWith('//')) continue;

        const parts = line.split(/[,\s\t]+/);
        if (parts.length >= 2) {
          const xVal = parseFloat(parts[0]);
          const yVal = parseFloat(parts[1]);
          if (!isNaN(xVal) && !isNaN(yVal)) {
            parsedX.push(xVal);
            parsedY.push(yVal);
          }
        }
      }

      if (parsedX.length > 0) {
        setXExp(parsedX);
        setYExp(parsedY);
        setFileName(file.name);
        setResult(null);
        setErrorMsg(null);
      } else {
        setErrorMsg("No se pudieron extraer datos de reflectancia del archivo. Asegúrate de tener dos columnas (X, Y).");
      }
    };
    reader.readAsText(file);
  };

  const addParameter = () => {
    const defaultIdx = 1;
    const currentD = layers[defaultIdx]?.d || 50;
    
    setParams([
      ...params,
      {
        id: Math.random().toString(36).substring(2, 9),
        layerIndex: defaultIdx,
        parameter: 'd',
        guess: currentD,
        minVal: Math.max(0, currentD - 20),
        maxVal: currentD + 20
      }
    ]);
  };

  const removeParameter = (id: string) => {
    setParams(params.filter(p => p.id !== id));
  };

  const updateParam = (id: string, field: keyof ActiveParam, val: any) => {
    setParams(params.map(p => {
      if (p.id !== id) return p;
      const updated = { ...p, [field]: val };
      
      // Auto-update guess and bounds when switching layers or parameters
      if (field === 'layerIndex' || field === 'parameter') {
        const layer = layers[updated.layerIndex];
        let baseVal = 0;
        if (updated.parameter === 'd') {
          baseVal = layer?.d || 0;
        } else if (updated.parameter === 'n') {
          baseVal = layer?.custom_n !== undefined ? layer.custom_n : 1.5;
        } else if (updated.parameter === 'k') {
          baseVal = layer?.custom_k !== undefined ? layer.custom_k : 0.0;
        }
        
        updated.guess = baseVal;
        updated.minVal = updated.parameter === 'd' ? Math.max(0, baseVal - 20) : Math.max(0, baseVal - 0.5);
        updated.maxVal = updated.parameter === 'd' ? baseVal + 20 : baseVal + 0.5;
      }
      
      return updated;
    }));
  };

  const handleFit = async () => {
    if (xExp.length === 0) {
      setErrorMsg("Por favor, sube un archivo con datos experimentales primero.");
      return;
    }
    if (params.length === 0) {
      setErrorMsg("Debe configurar al menos un parámetro para ajustar.");
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    const backendParams: FitParameterConfig[] = params.map(p => ({
      layer_index: p.layerIndex,
      parameter: p.parameter,
      guess: Number(p.guess),
      min_val: Number(p.minVal),
      max_val: Number(p.maxVal)
    }));

    try {
      const res = await fitCurve({
        layers,
        wavelength_nm: wavelength,
        polarization,
        interrogation_mode: interrogationMode,
        fixed_angle_deg: fixedAngle,
        x_exp: xExp,
        y_exp: yExp,
        parameters: backendParams
      });
      setResult(res);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.response?.data?.detail || err.message || "Error en el ajuste de curvas.");
    } finally {
      setLoading(false);
    }
  };

  const applyOptimizedDesign = () => {
    if (!result) return;
    
    const updatedLayers = [...layers];
    result.optimized_parameters.forEach(p => {
      const idx = p.layer_index;
      if (p.parameter === 'd') {
        updatedLayers[idx].d = Number(p.optimized_value?.toFixed(2));
      } else if (p.parameter === 'n') {
        updatedLayers[idx].custom_n = Number(p.optimized_value?.toFixed(4));
        updatedLayers[idx].material = 'Personalizado (Manual)';
      } else if (p.parameter === 'k') {
        updatedLayers[idx].custom_k = Number(p.optimized_value?.toFixed(4));
        updatedLayers[idx].material = 'Personalizado (Manual)';
      }
    });

    setLayers(updatedLayers);
    alert("¡Diseño optimizado aplicado exitosamente al editor de capas!");
  };

  // Prepare chart data
  const chartData = xExp.map((x, idx) => ({
    xVal: x,
    experimental: yExp[idx],
    simulated: result ? result.y_sim[idx] : undefined,
    initial: result ? result.y_initial[idx] : undefined
  }));

  // Sort chart data by X-value so that Recharts connects lines correctly
  chartData.sort((a, b) => a.xVal - b.xVal);

  return (
    <Box>
      <Typography variant="subtitle2" color="textSecondary" sx={{ mb: 3 }}>
        Carga y ajusta curvas experimentales frente a simulaciones teóricas usando algoritmos de mínimos cuadrados. Ideal para calibración de espesores reales o identificación de índices de refracción del analito.
      </Typography>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 5 }}>
          {/* File Upload Card */}
          <Paper variant="outlined" sx={{ p: 2.5, mb: 3, bgcolor: '#fafafa' }}>
            <Typography variant="body1" sx={{ fontWeight: 'bold', mb: 2 }}>
              1. Cargar Datos Experimentales
            </Typography>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
              <Button
                variant="outlined"
                component="label"
                startIcon={<UploadFileIcon />}
                sx={{ textTransform: 'none' }}
              >
                Seleccionar CSV / TXT
                <input
                  type="file"
                  accept=".csv,.txt"
                  hidden
                  onChange={handleFileUpload}
                />
              </Button>
              <Typography variant="caption" color="textSecondary">
                Formato: 2 columnas (X, Y) separadas por comas, espacios o tabuladores.
              </Typography>
            </Stack>

            {fileName && (
              <Box sx={{ mt: 2, p: 1.5, bgcolor: '#e3f2fd', borderRadius: 1 }}>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  Archivo: {fileName}
                </Typography>
                <Typography variant="caption" color="textSecondary" sx={{ display: 'block' }}>
                  Puntos detectados: {xExp.length}
                </Typography>
                <Typography variant="caption" color="textSecondary" sx={{ display: 'block' }}>
                  Rango X: [{Math.min(...xExp).toFixed(1)} - {Math.max(...xExp).toFixed(1)}]
                </Typography>
              </Box>
            )}
          </Paper>

          {/* Parameters to Fit Card */}
          <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
            <Stack direction="row" sx={{ mb: 2, justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                2. Configurar Parámetros a Ajustar
              </Typography>
              <Button
                size="small"
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={addParameter}
                sx={{ textTransform: 'none' }}
              >
                Añadir
              </Button>
            </Stack>

            {params.length === 0 ? (
              <Alert severity="warning" sx={{ mb: 2 }}>
                Agrega al menos un parámetro (espesor o refracción) para realizar el ajuste.
              </Alert>
            ) : (
              <TableContainer sx={{ maxHeight: 300 }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 'bold' }}>Capa</TableCell>
                      <TableCell sx={{ fontWeight: 'bold' }}>Var</TableCell>
                      <TableCell sx={{ fontWeight: 'bold' }}>Inicial</TableCell>
                      <TableCell sx={{ fontWeight: 'bold' }}>Lím. Inf</TableCell>
                      <TableCell sx={{ fontWeight: 'bold' }}>Lím. Sup</TableCell>
                      <TableCell sx={{ fontWeight: 'bold', width: 40 }}></TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {params.map((p) => (
                      <TableRow key={p.id}>
                        {/* Layer Selector */}
                        <TableCell sx={{ p: 0.5 }}>
                          <TextField
                            select
                            size="small"
                            value={p.layerIndex}
                            onChange={(e) => updateParam(p.id, 'layerIndex', Number(e.target.value))}
                            sx={{ width: 110 }}
                          >
                            {layers.map((l, idx) => (
                              <MenuItem key={idx} value={idx}>
                                {idx}: {l.material.substring(0, 12)}
                              </MenuItem>
                            ))}
                          </TextField>
                        </TableCell>
                        
                        {/* Parameter Selector */}
                        <TableCell sx={{ p: 0.5 }}>
                          <TextField
                            select
                            size="small"
                            value={p.parameter}
                            onChange={(e) => updateParam(p.id, 'parameter', e.target.value)}
                            sx={{ width: 60 }}
                          >
                            <MenuItem value="d">d</MenuItem>
                            <MenuItem value="n">n</MenuItem>
                            <MenuItem value="k">k</MenuItem>
                          </TextField>
                        </TableCell>

                        {/* Guess */}
                        <TableCell sx={{ p: 0.5 }}>
                          <TextField
                            type="number"
                            size="small"
                            value={p.guess}
                            onChange={(e) => updateParam(p.id, 'guess', Number(e.target.value))}
                            sx={{ width: 70 }}
                          />
                        </TableCell>

                        {/* Min Bound */}
                        <TableCell sx={{ p: 0.5 }}>
                          <TextField
                            type="number"
                            size="small"
                            value={p.minVal}
                            onChange={(e) => updateParam(p.id, 'minVal', Number(e.target.value))}
                            sx={{ width: 70 }}
                          />
                        </TableCell>

                        {/* Max Bound */}
                        <TableCell sx={{ p: 0.5 }}>
                          <TextField
                            type="number"
                            size="small"
                            value={p.maxVal}
                            onChange={(e) => updateParam(p.id, 'maxVal', Number(e.target.value))}
                            sx={{ width: 70 }}
                          />
                        </TableCell>

                        {/* Delete Button */}
                        <TableCell sx={{ p: 0.5 }}>
                          <IconButton size="small" color="error" onClick={() => removeParameter(p.id)}>
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Paper>

          {/* Fit Controls */}
          <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
            <Button
              variant="contained"
              color="primary"
              fullWidth
              startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <PlayArrowIcon />}
              onClick={handleFit}
              disabled={loading || xExp.length === 0}
              sx={{ py: 1.2, fontWeight: 'bold' }}
            >
              {loading ? 'Ajustando Curva...' : 'Iniciar Ajuste'}
            </Button>
          </Stack>

          {errorMsg && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {errorMsg}
            </Alert>
          )}

          {/* Results Details Card */}
          {result && (
            <Card variant="outlined" sx={{ p: 2.5, borderLeft: '5px solid #1976d2', bgcolor: '#eef5fc' }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 1.5, color: '#1565c0' }}>
                Resultados del Ajuste Exitoso
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                Error residual del modelo (RMSE): <strong>{(result.rmse * 100).toFixed(3)} %</strong>
              </Typography>

              <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 'bold' }}>Capa</TableCell>
                      <TableCell sx={{ fontWeight: 'bold' }}>Var</TableCell>
                      <TableCell sx={{ fontWeight: 'bold' }}>Inicial</TableCell>
                      <TableCell sx={{ fontWeight: 'bold' }}>Ajustado</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {result.optimized_parameters.map((p, idx) => {
                      const layerMat = layers[p.layer_index]?.material || "Capa";
                      const label = p.parameter === 'd' ? 'nm' : '';
                      return (
                        <TableRow key={idx}>
                          <TableCell>{p.layer_index}: {layerMat.substring(0, 10)}</TableCell>
                          <TableCell>{p.parameter}</TableCell>
                          <TableCell>{p.guess} {label}</TableCell>
                          <TableCell sx={{ fontWeight: 'bold', color: 'success.main' }}>
                            {p.optimized_value?.toFixed(p.parameter === 'd' ? 2 : 4)} {label}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>

              <Button
                variant="contained"
                color="success"
                fullWidth
                startIcon={<CheckCircleIcon />}
                onClick={applyOptimizedDesign}
                sx={{ textTransform: 'none', fontWeight: 'bold' }}
              >
                Aplicar al Editor de Capas
              </Button>
            </Card>
          )}
        </Grid>

        {/* Chart Card */}
        <Grid size={{ xs: 12, md: 7 }}>
          <Paper variant="outlined" sx={{ p: 2.5, height: '100%', minHeight: 450, display: 'flex', flexDirection: 'column' }}>
            <Typography variant="body1" sx={{ fontWeight: 'bold', mb: 2 }}>
              Ajuste Gráfico: Datos Experimentales vs Ajustados
            </Typography>

            {xExp.length === 0 ? (
              <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#fafafa', border: '2px dashed #e0e0e0', borderRadius: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Sube un archivo de datos experimentales para visualizar el ajuste gráfico.
                </Typography>
              </Box>
            ) : (
              <Box sx={{ flexGrow: 1, height: 400 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 15, right: 30, left: 10, bottom: 25 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis 
                      dataKey="xVal" 
                      type="number"
                      domain={['auto', 'auto']}
                      tick={{ fontSize: 11 }}
                    >
                      <Label value={interrogationMode === 'angular' ? "Ángulo de Incidencia (deg)" : "Longitud de Onda (nm)"} offset={-15} position="insideBottom" />
                    </XAxis>
                    <YAxis tick={{ fontSize: 11 }}>
                      <Label value="Reflectancia (R)" angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} />
                    </YAxis>
                    <Tooltip 
                      formatter={(val: any) => Number(val).toFixed(5)}
                      labelFormatter={(label: any) => `X: ${Number(label).toFixed(2)}`}
                    />
                    <Legend verticalAlign="top" height={36} />
                    
                    {/* Experimental data as dots */}
                    <Line 
                      type="monotone" 
                      dataKey="experimental" 
                      name="Experimental (CSV)" 
                      stroke="#8884d8" 
                      dot={{ r: 2 }}
                      strokeDasharray="3 3"
                      activeDot={{ r: 4 }}
                    />
                    
                    {/* Initial guess simulation */}
                    {result && (
                      <Line 
                        type="monotone" 
                        dataKey="initial" 
                        name="Ajuste Inicial" 
                        stroke="#e0e0e0" 
                        dot={false}
                        strokeWidth={1.5}
                      />
                    )}

                    {/* Optimized simulation */}
                    {result && (
                      <Line 
                        type="monotone" 
                        dataKey="simulated" 
                        name="Ajuste Optimizado (Fitted)" 
                        stroke="#1976d2" 
                        dot={false}
                        strokeWidth={2.5}
                      />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              </Box>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default CurveFittingPanel;
