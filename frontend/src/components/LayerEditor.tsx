import React, { useState } from 'react';
import { 
  Box, IconButton, TextField, MenuItem, Button, Typography, Divider, Checkbox, FormControlLabel, CircularProgress,
  Stack, Dialog, DialogTitle, DialogContent, DialogActions
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import type { LayerConfig } from '../types';
import { optimizeStructure, importMaterial } from '../api/client';
import type { MaterialInfo } from '../api/client';

interface Props {
  layers: LayerConfig[];
  setLayers: React.Dispatch<React.SetStateAction<LayerConfig[]>>;
  wavelength: number;
  polarization: 'TM' | 'TE';
  materialsList: MaterialInfo[];
  refreshMaterials: () => Promise<void>;
}

const DEFAULT_MATERIALS = [
    "Aire / Vacío", "Agua (H2O)", "Vidrio (BK7)", "Sílice (Silica)", 
    "Oro (Au)", "Oro (Au) - Johnson & Christy", "Plata (Ag)", "Plata (Ag) - Johnson & Christy", 
    "Aluminio (Al)", "Cromo (Cr)", "Titanio (Ti)", "Cobre (Cu) - Johnson & Christy", 
    "Silicio (Si) - Green", "Dióxido de Estaño (SnO2)", "Disulfuro de Tungsteno (WS2)", 
    "MoS2 (Disulfuro de Molibdeno)", "ITO (Óxido de Indio y Estaño)", "Grafeno", "Personalizado (Manual)"
];

const LayerEditor: React.FC<Props> = ({ 
  layers, setLayers, wavelength, polarization, materialsList, refreshMaterials 
}) => {
  const [optIndices, setOptIndices] = useState<number[]>([]);
  const [optimizing, setOptimizing] = useState(false);
  const [optTarget, setOptTarget] = useState<string>('Minimizar Reflectancia');
  
  // Custom optimization bounds state
  const [minBounds, setMinBounds] = useState<{[key: number]: number}>({});
  const [maxBounds, setMaxBounds] = useState<{[key: number]: number}>({});

  // Material import state
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importName, setImportName] = useState('');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);

  // Material dropdown options
  const displayMaterials = materialsList && materialsList.length > 0 
    ? materialsList.map(m => m.name) 
    : DEFAULT_MATERIALS;

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
        bounds_max,
        target: optTarget
      });
      setLayers(result.optimized_layers);
    } catch (error) {
      console.error("Optimization failed", error);
      alert("Error optimizando la estructura. Revisa los límites y configuraciones.");
    }
    setOptimizing(false);
  };

  const handleImportMaterialSubmit = async () => {
    if (!importFile || !importName.trim()) {
      alert("Por favor, selecciona un archivo CSV y especifica un nombre para el material.");
      return;
    }
    setImporting(true);
    try {
      await importMaterial(importFile, importName.trim());
      await refreshMaterials();
      alert(`Material '${importName}' importado con éxito.`);
      setImportDialogOpen(false);
      setImportName('');
      setImportFile(null);
    } catch (error: any) {
      console.error("Material import failed:", error);
      alert("Error al importar material: " + (error.response?.data?.detail || error.message));
    } finally {
      setImporting(false);
    }
  };

  return (
    <Box>
      <Stack direction="row" spacing={2} sx={{ mb: 3, alignItems: 'center' }}>
        <TextField
          select
          label="Cargar Plantilla de Sensor"
          size="small"
          sx={{ width: '100%', maxWidth: 300 }}
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

        <Button
          variant="outlined"
          color="info"
          startIcon={<CloudUploadIcon />}
          onClick={() => setImportDialogOpen(true)}
          sx={{ height: 40 }}
        >
          Importar Material (.csv)
        </Button>
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
                value={layer.is_effective_medium ? 'Personalizado (Manual)' : layer.material}
                onChange={(e) => updateLayer(index, 'material', e.target.value)}
                disabled={layer.is_effective_medium}
              >
                {displayMaterials.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
              </TextField>
            </Box>
            <Box sx={{ flex: 1.5, minWidth: 100 }}>
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
            {layer.material === 'Grafeno' && (
              <Box sx={{ flex: 1, minWidth: 80 }}>
                <TextField
                  fullWidth
                  label="N° Capas"
                  type="number"
                  size="small"
                  value={layer.custom_layers || 1}
                  onChange={(e) => updateLayer(index, 'custom_layers', Number(e.target.value))}
                />
              </Box>
            )}
            <Box sx={{ flex: 1.1, minWidth: 105 }}>
              {index !== 0 && index !== layers.length - 1 && (
                <FormControlLabel
                  control={<Checkbox checked={optIndices.includes(index)} onChange={() => toggleOpt(index)} />}
                  label="Optimizar"
                />
              )}
            </Box>
            <Box sx={{ flex: 1.3, minWidth: 125 }}>
              {index !== 0 && index !== layers.length - 1 && (
                <FormControlLabel
                  control={
                    <Checkbox 
                      checked={layer.is_effective_medium || false} 
                      onChange={(e) => {
                        const isChecked = e.target.checked;
                        updateLayer(index, 'is_effective_medium', isChecked);
                        if (isChecked) {
                          if (!layer.matrix_material) updateLayer(index, 'matrix_material', 'Vidrio (BK7)');
                          if (!layer.inclusion_material) updateLayer(index, 'inclusion_material', 'Aire / Vacio');
                          if (!layer.model_type) updateLayer(index, 'model_type', 'bruggeman');
                          if (layer.fraction === undefined) updateLayer(index, 'fraction', 0.5);
                        }
                      }} 
                    />
                  }
                  label="M. Efectivo"
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
          {(layer.material === 'Personalizado (Manual)' || layer.material === 'Grafeno' || optIndices.includes(index) || layer.is_effective_medium) && (
            <Stack direction="column" spacing={1.5} sx={{ mt: 1.5, pl: 12 }}>
              <Stack direction="row" spacing={3} sx={{ alignItems: 'center', flexWrap: 'wrap', gap: 1.5 }}>
                {layer.material === 'Personalizado (Manual)' && !layer.is_effective_medium && (
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
                {layer.material === 'Grafeno' && !layer.is_effective_medium && (
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
              
              {layer.is_effective_medium && (
                <Stack direction="column" spacing={1} sx={{ width: '100%' }}>
                  <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
                    CONFIGURACIÓN DE MEDIO EFECTIVO (MEZCLA DE MATERIALES)
                  </Typography>
                  <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', gap: 1.5, alignItems: 'center' }}>
                    <TextField
                      select
                      label="Matriz (Huésped)"
                      size="small"
                      sx={{ width: 180 }}
                      value={layer.matrix_material || 'Vidrio (BK7)'}
                      onChange={(e) => updateLayer(index, 'matrix_material', e.target.value)}
                    >
                      {displayMaterials.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
                    </TextField>
                    
                    <TextField
                      select
                      label="Inclusión"
                      size="small"
                      sx={{ width: 180 }}
                      value={layer.inclusion_material || 'Aire / Vacio'}
                      onChange={(e) => updateLayer(index, 'inclusion_material', e.target.value)}
                    >
                      {displayMaterials.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
                    </TextField>
                    
                    <TextField
                      select
                      label="Modelo"
                      size="small"
                      sx={{ width: 160 }}
                      value={layer.model_type || 'bruggeman'}
                      onChange={(e) => updateLayer(index, 'model_type', e.target.value)}
                    >
                      <MenuItem value="bruggeman">Bruggeman</MenuItem>
                      <MenuItem value="maxwell-garnett">Maxwell-Garnett</MenuItem>
                    </TextField>
                    
                    <TextField
                      label="Fracción Vol. f (Inclusión)"
                      type="number"
                      size="small"
                      slotProps={{ htmlInput: { step: 0.05, min: 0.0, max: 1.0 } }}
                      sx={{ width: 180 }}
                      value={layer.fraction !== undefined ? layer.fraction : 0.5}
                      onChange={(e) => updateLayer(index, 'fraction', Number(e.target.value))}
                    />
                  </Stack>
                  {layer.model_type === 'maxwell-garnett' && (layer.fraction ?? 0.5) > 0.3 && (
                    <Typography variant="caption" color="warning.main" sx={{ fontWeight: 'bold', mt: 0.5 }}>
                      ⚠️ Advertencia: El modelo de Maxwell-Garnett pierde precisión física para f &gt; 0.3. Se recomienda usar Bruggeman.
                    </Typography>
                  )}
                </Stack>
              )}
            </Stack>
          )}

          {index < layers.length - 1 && <Divider sx={{ mt: 2 }} />}
        </Box>
      ))}
      <Stack component="div" direction="row" spacing={2} sx={{ mt: 2, alignItems: 'center' }}>
        <Button 
          startIcon={<AddIcon />} 
          variant="outlined" 
          onClick={addLayer}
        >
          Añadir Capa
        </Button>
        <TextField
          select
          label="Objetivo de Optimización"
          value={optTarget}
          onChange={(e) => setOptTarget(e.target.value)}
          size="small"
          sx={{ width: 220 }}
          disabled={optimizing}
        >
          <MenuItem value="Minimizar Reflectancia">Minimizar Reflectancia</MenuItem>
          <MenuItem value="Maximizar Sensibilidad">Maximizar Sensibilidad</MenuItem>
          <MenuItem value="Maximizar FoM">Maximizar FoM</MenuItem>
        </TextField>
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

      {/* Dialog for Importing Materials */}
      <Dialog open={importDialogOpen} onClose={() => setImportDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Importar Material desde RefractiveIndex.info</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 3, mt: 1 }}>
            Sube un archivo <strong>CSV (Data)</strong> descargado directamente de <a href="https://refractiveindex.info" target="_blank" rel="noreferrer">refractiveindex.info</a>. El sistema interpretará automáticamente las constantes ópticas n y k y las longitudes de onda en micras.
          </Typography>
          <Stack spacing={3}>
            <TextField
              fullWidth
              label="Nombre del Material"
              placeholder="Ej: Cobre (Cu) - Johnson, ZnO - ALD"
              value={importName}
              onChange={(e) => setImportName(e.target.value)}
            />
            <Button
              variant="outlined"
              component="label"
              startIcon={<CloudUploadIcon />}
              fullWidth
              sx={{ py: 1.5 }}
            >
              {importFile ? `Archivo seleccionado: ${importFile.name}` : 'Seleccionar Archivo CSV'}
              <input 
                type="file" 
                accept=".csv" 
                hidden 
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setImportFile(e.target.files[0]);
                    if (!importName) {
                      const nameGuess = e.target.files[0].name.replace('.csv', '').replace(/_/g, ' ');
                      setImportName(nameGuess);
                    }
                  }
                }} 
              />
            </Button>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button onClick={() => setImportDialogOpen(false)} disabled={importing}>
            Cancelar
          </Button>
          <Button 
            onClick={handleImportMaterialSubmit} 
            variant="contained" 
            color="primary"
            disabled={importing || !importFile || !importName.trim()}
          >
            {importing ? <CircularProgress size={20} /> : 'Importar y Registrar'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default LayerEditor;
