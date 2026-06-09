import React from 'react';
import { Box, Paper, Typography } from '@mui/material';
import type { LayerConfig } from '../types';

interface Props {
  layers: LayerConfig[];
}

// Colors dictionary for the materials
const getMaterialColor = (material: string) => {
  switch (material) {
    case "Vidrio (BK7)":
    case "Sílice (Silica)":
      return { fill: "url(#glassGrad)", stroke: "#00acc1" };
    case "Oro (Au)":
      return { fill: "url(#goldGrad)", stroke: "#ffb300" };
    case "Plata (Ag)":
      return { fill: "url(#silverGrad)", stroke: "#b0bec5" };
    case "Aluminio (Al)":
      return { fill: "#cfd8dc", stroke: "#90a4ae" };
    case "Cromo (Cr)":
      return { fill: "#90a4ae", stroke: "#607d8b" };
    case "Grafeno":
      return { fill: "#37474f", stroke: "#263238" };
    case "Agua (H2O)":
    case "Agua":
      return { fill: "url(#waterGrad)", stroke: "#29b6f6" };
    case "Aire / Vacío":
      return { fill: "#ffffff", stroke: "#e0e0e0" };
    default:
      return { fill: "url(#customGrad)", stroke: "#8e24aa" };
  }
};

const LayerSchematic: React.FC<Props> = ({ layers }) => {
  // We will build a stack of layers.
  // The first layer is the Substrate (Prism), drawn at the bottom.
  // The middle layers are drawn sequentially.
  // The last layer is the Superstrate (Sensing medium), drawn at the top.
  
  const width = 500;
  const height = 300;
  const totalLayers = layers.length;

  // Heights configuration
  const prismHeight = 80;
  const sensingHeight = 80;
  const availableHeight = height - prismHeight - sensingHeight;

  // Compute total thickness of thin-film layers to scale them
  const thinFilms = layers.slice(1, -1);
  const totalThinThickness = thinFilms.reduce((acc, curr) => acc + (curr.material === 'Grafeno' ? (curr.custom_layers || 1) * 0.34 : curr.d), 0);

  let currentY = height - prismHeight;

  const renderedLayers = layers.map((layer, index) => {
    let y = 0;
    let h = 0;
    let isInfinite = false;
    let label = layer.material;

    if (index === 0) {
      // Substrate (Prism) - Bottom
      y = height - prismHeight;
      h = prismHeight;
      isInfinite = true;
      label += " (Sustrato)";
    } else if (index === totalLayers - 1) {
      // Superstrate (Sensing medium) - Top
      y = 0;
      h = sensingHeight;
      isInfinite = true;
      label += " (Sensing)";
    } else {
      // Thin films in between (apilados de abajo hacia arriba desde el prisma)
      const thickness = layer.material === 'Grafeno' 
        ? (layer.custom_layers || 1) * 0.34 
        : layer.d;
        
      // Give each thin film a proportional size, but minimum 15px so it is visible
      const weight = totalThinThickness > 0 ? thickness / totalThinThickness : 1;
      h = Math.max(15, weight * availableHeight);
      
      currentY -= h;
      y = currentY;
      label += ` (${thickness.toFixed(1)} nm)`;
    }

    const colors = getMaterialColor(layer.material);

    return {
      index,
      y,
      h,
      label,
      isInfinite,
      ...colors
    };
  });

  // Laser beam coordinates (centered around the first metal interface)
  const interfaceY = height - prismHeight;
  const beamStartX = 50;
  const beamStartY = height - 20;
  const beamCenterX = width / 2;
  const beamCenterY = interfaceY;
  const beamEndX = width - 50;
  const beamEndY = height - 20;

  return (
    <Paper variant="outlined" sx={{ p: 2, bgcolor: '#fafafa', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 'bold', color: 'text.secondary' }}>
        Estructura Acoplador de Plasmón (Kretschmann)
      </Typography>
      <Box sx={{ width: '100%', maxWidth: width, position: 'relative' }}>
        <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} style={{ border: '1px solid #e0e0e0', borderRadius: 4, backgroundColor: '#fff' }}>
          <defs>
            {/* Gradients */}
            <linearGradient id="glassGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#e0f7fa" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#80deea" stopOpacity="0.8" />
            </linearGradient>
            <linearGradient id="goldGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#ffe082" />
              <stop offset="100%" stopColor="#ffb300" />
            </linearGradient>
            <linearGradient id="silverGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#f5f5f5" />
              <stop offset="100%" stopColor="#b0bec5" />
            </linearGradient>
            <linearGradient id="waterGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#e3f2fd" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#90caf9" stopOpacity="0.9" />
            </linearGradient>
            <linearGradient id="customGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#f3e5f5" />
              <stop offset="100%" stopColor="#ce93d8" />
            </linearGradient>
            <linearGradient id="laserGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#ff1744" stopOpacity="1" />
              <stop offset="100%" stopColor="#ff1744" stopOpacity="0.2" />
            </linearGradient>
          </defs>

          {/* Draw Layers */}
          {renderedLayers.map((l) => (
            <g key={l.index}>
              <rect
                x={0}
                y={l.y}
                width={width}
                height={l.h}
                fill={l.fill}
                stroke={l.stroke}
                strokeWidth={l.isInfinite ? 0 : 1}
              />
              <text
                x={15}
                y={l.index === 0 ? l.y + 20 : l.y + l.h / 2 + 5}
                fill="#37474f"
                fontSize={12}
                fontWeight="bold"
                style={{ pointerEvents: 'none' }}
              >
                {l.label}
              </text>
            </g>
          ))}

          {/* Draw Laser Beam (Incident and Reflected) */}
          {/* Incident Beam */}
          <line
            x1={beamStartX}
            y1={beamStartY}
            x2={beamCenterX}
            y2={beamCenterY}
            stroke="#ff1744"
            strokeWidth={3}
            strokeDasharray="none"
          />
          <polygon
            points={`${beamCenterX-10},${beamCenterY+15} ${beamCenterX},${beamCenterY} ${beamCenterX-15},${beamCenterY+5}`}
            fill="#ff1744"
          />
          
          {/* Reflected Beam */}
          <line
            x1={beamCenterX}
            y1={beamCenterY}
            x2={beamEndX}
            y2={beamEndY}
            stroke="#d500f9"
            strokeWidth={3}
            strokeDasharray="4 4"
          />

          {/* Text Labels for Laser */}
          <text x={beamStartX} y={beamStartY + 15} fill="#d50000" fontSize={11} fontWeight="bold">Luz Incidente</text>
          <text x={beamEndX - 90} y={beamEndY + 15} fill="#aa00ff" fontSize={11} fontWeight="bold">Reflectancia (R)</text>

          {/* SPR Resonance Indicator (Glow center point) */}
          <circle
            cx={beamCenterX}
            cy={beamCenterY}
            r={8}
            fill="#ff1744"
            opacity={0.6}
            style={{ animation: 'pulse 1.5s infinite alternate' }}
          />
        </svg>
      </Box>
    </Paper>
  );
};

export default LayerSchematic;
