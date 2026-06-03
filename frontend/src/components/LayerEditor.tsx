import React, { useState } from 'react';
import { 
  Box, IconButton, TextField, MenuItem, Button, Typography, Divider, Checkbox, FormControlLabel, CircularProgress,
  Stack
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import type { LayerConfig } from '../types';
import { optimizeStructure } from '../api/client';

interface Props {
  layers: LayerConfig[];
  setLayers: React.Dispatch<React.SetStateAction<LayerConfig[]>>;
  wavelength: number;
  polarization: 'TM' | 'TE';
}

const materials = [
    "Aire / Vacío", "Agua (H2O)", "Vidrio (BK7)", "Sílice (Silica)", 
    "Oro (Au)", "Plata (Ag)", "Aluminio (Al)", "Cromo (Cr)", "Grafeno", "Personalizado (Manual)"
];

const LayerEditor: React.FC<Props> = ({ layers, setLayers, wavelength, polarization }) => {
  const [optIndices, setOptIndices] = useState<number[]>([]);
  const [optimizing, setOptimizing] = useState(false);
  
  // Custom optimization bounds state
  const [minBounds, setMinBounds] = useState<{[key: number]: number}>({});
  const [maxBounds, setMaxBounds] = useState<{[key: number]: number}>({});

  const updateLayer = (index: number, field: keyof LayerConfig, value: any) => {
    const newLayers = [...layers];
    newLayers[index] = { ...newLayers[index], [field]: value };
    setLayers(newLayers);
  };

  const addLayer = () => {
    const newLayers = [...layers];
    newLayers.splice(newLayers.length - 1, 0, { material: 'Oro (Au)', d: 45 });
    setLayers(newLayers);
  };

  const removeLayer = (index: number) => {
    if (layers.length <= 2) return;
    const newLayers = layers.filter((_, i) => i !== index);
    setLayers(newLayers);
    setOptIndices(optIndices.filter(i => i !== index));
    
    // Clean up bounds
    const newMin = { ...minBounds };
    const newMax = { ...maxBounds };
    delete newMin[index];
    delete newMax[index];
    setMinBounds(newMin);
    setMaxBounds(newMax);
  };

  const toggleOpt = (index: number) => {
    if (optIndices.includes(index)) {
      setOptIndices(optIndices.filter(i => i !== index));
    } else {
      setOptIndices([...optIndices, index]);
    }
  };

  const handleOptimize = async () => {
    if (optIndices.length === 0) return;
    setOptimizing(true);
    
    const bounds_min = optIndices.map(idx => minBounds[idx] !== undefined ? minBounds[idx] : 20);
    const bounds_max = optIndices.map(idx => maxBounds[idx] !== undefined ? maxBounds[idx] : 90);

    try {
      const result = await optimizeStructure({
        wavelength_nm: wavelength,
        polarization,
        layers,
        optimize_indices: optIndices,
        bounds_min,
        bounds_max
      });
      setLayers(result.optimized_layers);
    } catch (error) {
      console.error("Optimization failed", error);
      alert("Error optimizando la estructura. Revisa los límites y configuraciones.");
    }
    setOptimizing(false);
  };

  return (
    <Box>
      <Stack direction="row" spacing={2} sx={{ mb: 3, alignItems: 'center' }}>
        <TextField
          select
          label="Cargar Plantilla de Sensor"
          size="small"
          sx={{ width: '100%', maxWidth: 350 }}
          value=""
          onChange={(e) => {
            const val = e.target.value;
            if (val === 'kretschmann') {
              setLayers([
                { material: 'Vidrio (BK7)', d: 0 },
                { material: 'Oro (Au)', d: 50 },
                { material: 'Aire / Vacío', d: 0 }
              ]);
            } else if (val === 'otto') {
              setLayers([
                { material: 'Vidrio (BK7)', d: 0 },
                { material: 'Aire / Vacío', d: 800 },
                { material: 'Oro (Au)', d: 45 },
                { material: 'Aire / Vacío', d: 0 }
              ]);
            } else if (val === 'waveguide') {
              setLayers([
                { material: 'Vidrio (BK7)', d: 0 },
                { material: 'Oro (Au)', d: 40 },
                { material: 'Sílice (Silica)', d: 100 },
                { material: 'Agua (H2O)', d: 0 }
              ]);
            } else if (val === 'graphene') {
              setLayers([
                { material: 'Vidrio (BK7)', d: 0 },
                { material: 'Oro (Au)', d: 45 },
                { material: 'Grafeno', d: 0.34, custom_layers: 3, custom_mu: 0.3 },
                { material: 'Agua (H2O)', d: 0 }
              ]);
            }
          }}
        >
          <MenuItem value="kretschmann">Kretschmann Estándar (Au, 50nm)</MenuItem>
          <MenuItem value="otto">Otto (Acoplamiento por Aire, 800nm)</MenuItem>
          <MenuItem value="waveguide">Guía de Onda WC-SPR (Au + SiO2)</MenuItem>
          <MenuItem value="graphene">Biosensor de Grafeno (Au + 3 capas G)</MenuItem>
        </TextField>
      </Stack>
      <Divider sx={{ mb: 3 }} />

      {layers.map((layer, index) => (
        <Box key={index} sx={{ mb: 2 }}>
          <Stack component="div" direction="row" spacing={2} sx={{ alignItems: 'center' }}>
            <Box sx={{ width: 80 }}>
              <Typography variant="subtitle1" component="span" sx={{ fontWeight: 'bold' }}>Capa {index}</Typography>
            </Box>
            <Box sx={{ flex: 2 }}>
              <TextField
                fullWidth
                select
                label="Material"
                size="small"
                value={layer.material}
                onChange={(e) => updateLayer(index, 'material', e.target.value)}
              >
                {materials.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
              </TextField>
            </Box>
            <Box sx={{ flex: 1 }}>
              {index !== 0 && index !== layers.length - 1 && (
                <TextField
                  fullWidth
                  label="Grosor (nm)"
                  type="number"
                  size="small"
                  value={layer.d}
                  onChange={(e) => updateLayer(index, 'd', Number(e.target.value))}
                />
              )}
              {(index === 0 || index === layers.length - 1) && (
                <Typography variant="body2" component="span" color="text.secondary">Semi-infinito</Typography>
              )}
            </Box>
            <Box sx={{ flex: 1 }}>
                {layer.material === 'Grafeno' && (
                    <TextField
                        fullWidth
                        label="N° Capas"
                        type="number"
                        size="small"
                        value={layer.custom_layers || 1}
                        onChange={(e) => updateLayer(index, 'custom_layers', Number(e.target.value))}
                    />
                )}
            </Box>
            <Box sx={{ flex: 1 }}>
              {index !== 0 && index !== layers.length - 1 && (
                <FormControlLabel
                  control={<Checkbox checked={optIndices.includes(index)} onChange={() => toggleOpt(index)} />}
                  label="Optimizar"
                />
              )}
            </Box>
            <Box>
              {index !== 0 && index !== layers.length - 1 && (
                <IconButton color="error" onClick={() => removeLayer(index)}>
                  <DeleteIcon />
                </IconButton>
              )}
            </Box>
          </Stack>

          {/* Conditional Sub-row for extra parameters */}
          {(layer.material === 'Personalizado (Manual)' || layer.material === 'Grafeno' || optIndices.includes(index)) && (
            <Stack direction="row" spacing={3} sx={{ mt: 1.5, pl: 12, alignItems: 'center' }}>
              {layer.material === 'Personalizado (Manual)' && (
                <>
                  <TextField
                    label="n (Real)"
                    type="number"
                    size="small"
                    slotProps={{ htmlInput: { step: 0.01 } }}
                    sx={{ width: 120 }}
                    value={layer.custom_n !== undefined ? layer.custom_n : 1.5}
                    onChange={(e) => updateLayer(index, 'custom_n', Number(e.target.value))}
                  />
                  <TextField
                    label="k (Imaginaria)"
                    type="number"
                    size="small"
                    slotProps={{ htmlInput: { step: 0.01 } }}
                    sx={{ width: 120 }}
                    value={layer.custom_k !== undefined ? layer.custom_k : 0.0}
                    onChange={(e) => updateLayer(index, 'custom_k', Number(e.target.value))}
                  />
                </>
              )}
              {layer.material === 'Grafeno' && (
                <TextField
                  label="Pot. Químico μ_c (eV)"
                  type="number"
                  size="small"
                  slotProps={{ htmlInput: { step: 0.05 } }}
                  sx={{ width: 160 }}
                  value={layer.custom_mu !== undefined ? layer.custom_mu : 0.3}
                  onChange={(e) => updateLayer(index, 'custom_mu', Number(e.target.value))}
                />
              )}
              {optIndices.includes(index) && (
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 'bold' }}>LÍMITES IA:</Typography>
                  <TextField
                    label="Mín (nm)"
                    type="number"
                    size="small"
                    sx={{ width: 90 }}
                    value={minBounds[index] !== undefined ? minBounds[index] : 20}
                    onChange={(e) => setMinBounds({ ...minBounds, [index]: Number(e.target.value) })}
                  />
                  <TextField
                    label="Máx (nm)"
                    type="number"
                    size="small"
                    sx={{ width: 90 }}
                    value={maxBounds[index] !== undefined ? maxBounds[index] : 90}
                    onChange={(e) => setMaxBounds({ ...maxBounds, [index]: Number(e.target.value) })}
                  />
                </Stack>
              )}
            </Stack>
          )}

          {index < layers.length - 1 && <Divider sx={{ mt: 2 }} />}
        </Box>
      ))}
      <Stack component="div" direction="row" spacing={2} sx={{ mt: 2 }}>
        <Button 
          startIcon={<AddIcon />} 
          variant="outlined" 
          onClick={addLayer}
        >
          Añadir Capa
        </Button>
        <Button 
          startIcon={optimizing ? <CircularProgress size={20} /> : <AutoFixHighIcon />} 
          variant="contained" 
          color="secondary"
          onClick={handleOptimize}
          disabled={optimizing || optIndices.length === 0}
        >
          IA: Optimizar Grosores
        </Button>
      </Stack>
    </Box>
  );
};

export default LayerEditor;

