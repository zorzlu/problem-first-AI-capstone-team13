import React, { useState } from 'react';
import type { ExposureGraph, GraphEdge, GraphNode } from '../types';

// ---------------------------------------------------------------------------
// Exposure-graph layout + rendering (shared by the sidebar card and the modal)
// ---------------------------------------------------------------------------
const MID_NODE_TYPES = ['technology_theme', 'private_company', 'sector'];

// Hybrid 1D force-directed layout to group connected components vertically,
// making lines more horizontal and using strict spacing constraints to prevent overlaps.
function computeLayout(nodes: GraphNode[], edges: GraphEdge[], width: number, height: number) {
  const padX = Math.max(38, width * 0.1);
  const padY = Math.max(24, height * 0.06);
  
  const leftNodes: GraphNode[] = [];
  const midNodes: GraphNode[] = [];
  const rightNodes: GraphNode[] = [];
  
  for (const n of nodes) {
    if (n.nodeType === 'ticker') rightNodes.push(n);
    else if (MID_NODE_TYPES.includes(n.nodeType)) midNodes.push(n);
    else leftNodes.push(n);
  }

  // 1. Right nodes (Tickers) are fixed. Assign them a baseline order (index)
  const rightPositions = new Map<string, number>();
  rightNodes.forEach((n, i) => {
    rightPositions.set(n.nodeId, i);
  });

  // 2. Middle nodes: calculate barycenter based on connections to Right nodes (Tickers)
  const midConnections = new Map<string, number[]>();
  for (const edge of edges) {
    const isFromMid = midNodes.some(n => n.nodeId === edge.fromNodeId);
    const isToRight = rightNodes.some(n => n.nodeId === edge.toNodeId);
    if (isFromMid && isToRight) {
      if (!midConnections.has(edge.fromNodeId)) midConnections.set(edge.fromNodeId, []);
      const rightIndex = rightPositions.get(edge.toNodeId) ?? 0;
      midConnections.get(edge.fromNodeId)!.push(rightIndex);
    }
  }

  const getBarycenter = (nodeId: string, connectionsMap: Map<string, number[]>, defaultVal: number) => {
    const list = connectionsMap.get(nodeId);
    if (!list || list.length === 0) return defaultVal;
    const sum = list.reduce((a, b) => a + b, 0);
    return sum / list.length;
  };

  // Sort middle nodes based on average target position
  const midWithBary = midNodes.map((n, i) => ({
    node: n,
    val: getBarycenter(n.nodeId, midConnections, i)
  }));
  midWithBary.sort((a, b) => a.val - b.val);
  const sortedMidNodes = midWithBary.map(x => x.node);

  // Map sorted middle node positions
  const midPositions = new Map<string, number>();
  sortedMidNodes.forEach((n, i) => {
    midPositions.set(n.nodeId, i);
  });

  // 3. Left nodes: calculate barycenter based on connections to Middle and Right nodes
  const leftConnections = new Map<string, number[]>();
  for (const edge of edges) {
    const isFromLeft = leftNodes.some(n => n.nodeId === edge.fromNodeId);
    if (isFromLeft) {
      const isToMid = sortedMidNodes.some(n => n.nodeId === edge.toNodeId);
      const isToRight = rightNodes.some(n => n.nodeId === edge.toNodeId);
      
      if (isToMid) {
        if (!leftConnections.has(edge.fromNodeId)) leftConnections.set(edge.fromNodeId, []);
        const midIndex = midPositions.get(edge.toNodeId) ?? 0;
        leftConnections.get(edge.fromNodeId)!.push(midIndex / Math.max(1, sortedMidNodes.length));
      } else if (isToRight) {
        if (!leftConnections.has(edge.fromNodeId)) leftConnections.set(edge.fromNodeId, []);
        const rightIndex = rightPositions.get(edge.toNodeId) ?? 0;
        leftConnections.get(edge.fromNodeId)!.push(rightIndex / Math.max(1, rightNodes.length));
      }
    }
  }

  // Sort left nodes based on average target position
  const leftWithBary = leftNodes.map((n, i) => ({
    node: n,
    val: getBarycenter(n.nodeId, leftConnections, i)
  }));
  leftWithBary.sort((a, b) => a.val - b.val);
  const sortedLeftNodes = leftWithBary.map(x => x.node);

  // Assign initial coordinates distributed vertically
  const xs = { left: padX, mid: width / 2, right: width - padX };
  const positions = new Map<string, { x: number; y: number }>();
  
  sortedLeftNodes.forEach((n, i) => {
    const y = padY + (height - 2 * padY) * (i + 1) / (sortedLeftNodes.length + 1);
    positions.set(n.nodeId, { x: xs.left, y });
  });

  sortedMidNodes.forEach((n, i) => {
    const y = padY + (height - 2 * padY) * (i + 1) / (sortedMidNodes.length + 1);
    positions.set(n.nodeId, { x: xs.mid, y });
  });

  rightNodes.forEach((n, i) => {
    const y = padY + (height - 2 * padY) * (i + 1) / (rightNodes.length + 1);
    positions.set(n.nodeId, { x: xs.right, y });
  });

  // 4. Force-directed Y refinement with overlap prevention constraints
  const yMap = new Map<string, number>();
  nodes.forEach(n => {
    const pos = positions.get(n.nodeId);
    if (pos) yMap.set(n.nodeId, pos.y);
  });

  const iterations = 150;
  const kAttract = 0.08;
  const kRepel = 2000;
  const minSpacing = 30; // Minimum vertical spacing between centers to prevent label overlap

  for (let step = 0; step < iterations; step++) {
    const forces = new Map<string, number>();
    nodes.forEach(n => forces.set(n.nodeId, 0));

    // Repulsion within the same column
    const repelColumn = (colNodes: GraphNode[]) => {
      for (let i = 0; i < colNodes.length; i++) {
        for (let j = i + 1; j < colNodes.length; j++) {
          const n1 = colNodes[i];
          const n2 = colNodes[j];
          const y1 = yMap.get(n1.nodeId)!;
          const y2 = yMap.get(n2.nodeId)!;
          const diff = y1 - y2;
          const dist = Math.abs(diff);
          if (dist < 0.1) continue;
          
          let forceVal = kRepel / (dist * dist);
          if (forceVal > 50) forceVal = 50; // Cap maximum force to maintain stability
          
          if (diff > 0) {
            forces.set(n1.nodeId, forces.get(n1.nodeId)! + forceVal);
            forces.set(n2.nodeId, forces.get(n2.nodeId)! - forceVal);
          } else {
            forces.set(n1.nodeId, forces.get(n1.nodeId)! - forceVal);
            forces.set(n2.nodeId, forces.get(n2.nodeId)! + forceVal);
          }
        }
      }
    };

    repelColumn(sortedLeftNodes);
    repelColumn(sortedMidNodes);
    repelColumn(rightNodes);

    // Attraction along connections
    edges.forEach(edge => {
      const yFrom = yMap.get(edge.fromNodeId);
      const yTo = yMap.get(edge.toNodeId);
      if (yFrom === undefined || yTo === undefined) return;

      const diff = yFrom - yTo;
      const forceVal = diff * kAttract;

      forces.set(edge.fromNodeId, forces.get(edge.fromNodeId)! - forceVal);
      forces.set(edge.toNodeId, forces.get(edge.toNodeId)! + forceVal);
    });

    // Update coordinates based on forces
    nodes.forEach(n => {
      const currY = yMap.get(n.nodeId)!;
      yMap.set(n.nodeId, currY + forces.get(n.nodeId)!);
    });

    // Enforce spacing constraints within columns
    const enforceSpacing = (colNodes: GraphNode[]) => {
      if (colNodes.length === 0) return;
      const sorted = [...colNodes].sort((a, b) => yMap.get(a.nodeId)! - yMap.get(b.nodeId)!);
      
      // Sweep down to resolve spacing
      for (let i = 1; i < sorted.length; i++) {
        const prevY = yMap.get(sorted[i - 1].nodeId)!;
        const currY = yMap.get(sorted[i].nodeId)!;
        if (currY < prevY + minSpacing) {
          yMap.set(sorted[i].nodeId, prevY + minSpacing);
        }
      }
      
      // Sweep up to ensure bounds are respected
      const lastIdx = sorted.length - 1;
      if (yMap.get(sorted[lastIdx].nodeId)! > height - padY) {
        yMap.set(sorted[lastIdx].nodeId, height - padY);
        for (let i = lastIdx - 1; i >= 0; i--) {
          const nextY = yMap.get(sorted[i + 1].nodeId)!;
          const currY = yMap.get(sorted[i].nodeId)!;
          if (currY > nextY - minSpacing) {
            yMap.set(sorted[i].nodeId, nextY - minSpacing);
          }
        }
      }

      // Final clamp inside safe zone
      sorted.forEach(n => {
        let y = yMap.get(n.nodeId)!;
        if (y < padY) y = padY;
        if (y > height - padY) y = height - padY;
        yMap.set(n.nodeId, y);
      });
    };

    enforceSpacing(sortedLeftNodes);
    enforceSpacing(sortedMidNodes);
    enforceSpacing(rightNodes);
  }

  // Write refined Y positions back to output layout map
  nodes.forEach(n => {
    const pos = positions.get(n.nodeId);
    if (pos) {
      pos.y = yMap.get(n.nodeId)!;
    }
  });

  return positions;
}

function getNodeColor(nodeType: string, isHighlighted: boolean) {
  if (isHighlighted) return 'var(--accent-purple)';
  switch (nodeType) {
    case 'ticker': return 'var(--accent-purple)';
    case 'technology_theme': return 'var(--accent-blue)';
    case 'private_company': return 'var(--accent-cyan)';
    case 'sector': return 'var(--accent-cyan)';
    default: return 'var(--accent-orange)'; // region, risk_factor, shipping_route, commodity
  }
}

export const getTickerSymbol = (node: GraphNode): string | undefined => {
  if (node.nodeType !== 'ticker') return undefined;
  return node.ticker || (node.nodeId.startsWith('ticker_') ? node.nodeId.substring(7) : node.name);
};

const getRelevantGraphElements = (nodes: GraphNode[], edges: GraphEdge[], activeTicker: string) => {
  const relevantNodes = new Set<string>();
  const relevantEdges = new Set<string>();
  
  // Find the active ticker node
  const activeNode = nodes.find(n => n.nodeType === 'ticker' && getTickerSymbol(n) === activeTicker);
  if (!activeNode) return { relevantNodes, relevantEdges };
  
  relevantNodes.add(activeNode.nodeId);
  
  // Pass 1: find edges going directly into the active node, and add their source nodes
  for (const edge of edges) {
    if (edge.toNodeId === activeNode.nodeId) {
      relevantNodes.add(edge.fromNodeId);
      relevantEdges.add(`${edge.fromNodeId}->${edge.toNodeId}`);
    }
  }
  
  // Pass 2: find edges going into any of the currently relevant nodes
  for (const edge of edges) {
    if (relevantNodes.has(edge.toNodeId) && edge.toNodeId !== activeNode.nodeId) {
      relevantNodes.add(edge.fromNodeId);
      relevantEdges.add(`${edge.fromNodeId}->${edge.toNodeId}`);
    }
  }
  
  return { relevantNodes, relevantEdges };
};

// Trace upstream ancestors and downstream descendants of a clicked node
const getConnectedElements = (nodes: GraphNode[], edges: GraphEdge[], startNodeId: string) => {
  const connectedNodes = new Set<string>([startNodeId]);
  const connectedEdges = new Set<string>();
  
  // 1. Downstream (descendants): follow outgoing edges forward
  let queue = [startNodeId];
  const visitedDown = new Set<string>([startNodeId]);
  while (queue.length > 0) {
    const curr = queue.shift()!;
    for (const edge of edges) {
      if (edge.fromNodeId === curr && !visitedDown.has(edge.toNodeId)) {
        visitedDown.add(edge.toNodeId);
        connectedNodes.add(edge.toNodeId);
        connectedEdges.add(`${edge.fromNodeId}->${edge.toNodeId}`);
        queue.push(edge.toNodeId);
      }
    }
  }

  // 2. Upstream (ancestors): follow incoming edges backward
  queue = [startNodeId];
  const visitedUp = new Set<string>([startNodeId]);
  while (queue.length > 0) {
    const curr = queue.shift()!;
    for (const edge of edges) {
      if (edge.toNodeId === curr && !visitedUp.has(edge.fromNodeId)) {
        visitedUp.add(edge.fromNodeId);
        connectedNodes.add(edge.fromNodeId);
        connectedEdges.add(`${edge.fromNodeId}->${edge.toNodeId}`);
        queue.push(edge.fromNodeId);
      }
    }
  }
  
  // 3. Highlight edges connecting any two nodes in our set for completeness
  for (const edge of edges) {
    if (connectedNodes.has(edge.fromNodeId) && connectedNodes.has(edge.toNodeId)) {
      connectedEdges.add(`${edge.fromNodeId}->${edge.toNodeId}`);
    }
  }
  
  return { connectedNodes, connectedEdges };
};

export function GraphView({ graphData, width, height, scale = 1, selectedCatalystPath, activeTicker, watchlist = [] }: {
  graphData: ExposureGraph;
  width: number;
  height: number;
  scale?: number;
  selectedCatalystPath: string[] | null;
  activeTicker: string;
  watchlist?: string[];
}) {
  const [zoom, setZoom] = useState(1);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [clickedNodeId, setClickedNodeId] = useState<string | null>(null);

  if (graphData.nodes.length === 0) {
    return <div className="canvas-placeholder">Loading graph nodes...</div>;
  }

  const isNodeClicked = clickedNodeId !== null;
  const isFiltered = activeTicker && activeTicker !== 'dashboard';
  
  // Compute sets for filtering & click highlight
  const { connectedNodes, connectedEdges } = isNodeClicked
    ? getConnectedElements(graphData.nodes, graphData.edges, clickedNodeId)
    : { connectedNodes: new Set<string>(), connectedEdges: new Set<string>() };

  const { relevantNodes, relevantEdges } = isFiltered 
    ? getRelevantGraphElements(graphData.nodes, graphData.edges, activeTicker)
    : { relevantNodes: new Set<string>(), relevantEdges: new Set<string>() };

  // Separate nodes into columns to determine density
  const cols = { left: 0, mid: 0, right: 0 };
  for (const n of graphData.nodes) {
    if (n.nodeType === 'ticker') cols.right++;
    else if (MID_NODE_TYPES.includes(n.nodeType)) cols.mid++;
    else cols.left++;
  }
  const maxColLength = Math.max(cols.left, cols.mid, cols.right);
  
  // Calculate dynamic canvas height to avoid squishing labels
  const spacingPerNode = 32; // px per node
  const dynamicHeight = Math.max(height, maxColLength * spacingPerNode + 80);

  const positions = computeLayout(graphData.nodes, graphData.edges, width, dynamicHeight);
  const fontSize = 6.5 * scale;
  const nodeById = new Map(graphData.nodes.map(n => [n.nodeId, n]));

  // Event handlers for drag & pan
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - panX, y: e.clientY - panY });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPanX(e.clientX - dragStart.x);
    setPanY(e.clientY - dragStart.y);
    // Remove active text selection ranges to prevent accidental highlights while panning
    window.getSelection()?.removeAllRanges();
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Event handler for wheel zoom
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = 1.05;
    let newZoom = zoom;
    if (e.deltaY < 0) {
      newZoom = Math.min(zoom * zoomFactor, 8); // max zoom 8x
    } else {
      newZoom = Math.max(zoom / zoomFactor, 0.3); // min zoom 0.3x
    }
    setZoom(newZoom);
  };

  const handleZoomIn = () => setZoom(z => Math.min(z * 1.2, 8));
  const handleZoomOut = () => setZoom(z => Math.max(z / 1.2, 0.3));
  const handleZoomReset = () => {
    setZoom(1);
    setPanX(0);
    setPanY(0);
  };

  return (
    <div 
      className="graph-canvas"
      style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}
      onWheel={handleWheel}
    >
      <svg 
        width="100%" 
        height="100%" 
        viewBox={`0 0 ${width} ${dynamicHeight}`} 
        preserveAspectRatio="xMidYMid meet" 
        style={{ 
          background: 'var(--bg-primary)', 
          cursor: isDragging ? 'grabbing' : 'grab'
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onClick={() => setClickedNodeId(null)}
      >
        <defs>
          <marker 
            id="arrow" 
            viewBox="0 0 10 10" 
            refX="14" 
            refY="5" 
            markerWidth="5" 
            markerHeight="5" 
            orient="auto-start-reverse"
          >
            <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#71717a" />
          </marker>
          <marker 
            id="arrow-highlight" 
            viewBox="0 0 10 10" 
            refX="14" 
            refY="5" 
            markerWidth="6" 
            markerHeight="6" 
            orient="auto-start-reverse"
          >
            <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="var(--accent-purple)" />
          </marker>
          <marker 
            id="arrow-cyan" 
            viewBox="0 0 10 10" 
            refX="14" 
            refY="5" 
            markerWidth="6" 
            markerHeight="6" 
            orient="auto-start-reverse"
          >
            <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="var(--accent-cyan)" />
          </marker>
          <marker 
            id="arrow-dim" 
            viewBox="0 0 10 10" 
            refX="14" 
            refY="5" 
            markerWidth="4" 
            markerHeight="4" 
            orient="auto-start-reverse"
          >
            <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#e5e7eb" />
          </marker>
        </defs>

        <g transform={`translate(${panX}, ${panY}) scale(${zoom})`}>
          {/* Edges */}
          {graphData.edges.map((edge, idx) => {
            const fromPos = positions.get(edge.fromNodeId);
            const toPos = positions.get(edge.toNodeId);
            if (!fromPos || !toPos) return null;

            let isHighlighted = false;
            if (selectedCatalystPath) {
              const fromNode = nodeById.get(edge.fromNodeId);
              const toNode = nodeById.get(edge.toNodeId);
              if (fromNode && toNode) {
                const fromIdx = selectedCatalystPath.indexOf(fromNode.name);
                const toIdx = selectedCatalystPath.indexOf(toNode.name);
                if (fromIdx !== -1 && toIdx !== -1 && Math.abs(fromIdx - toIdx) === 1) isHighlighted = true;
              }
            }

            // Filter status
            const edgeKey = `${edge.fromNodeId}->${edge.toNodeId}`;
            
            let opacity = 0.5;
            let strokeColor = 'var(--text-muted)';
            let markerUrl = 'url(#arrow)';
            let strokeWidth = 1;

            if (isNodeClicked) {
              const isRelevant = connectedEdges.has(edgeKey);
              opacity = isRelevant ? 0.95 : 0.03;
              strokeColor = isRelevant ? 'var(--accent-purple)' : 'var(--border-color)';
              markerUrl = isRelevant ? 'url(#arrow-highlight)' : 'url(#arrow-dim)';
              strokeWidth = isRelevant ? 2.5 : 1;
            } else if (isFiltered) {
              const isRelevant = relevantEdges.has(edgeKey);
              opacity = isRelevant ? 0.85 : 0.05;
              strokeColor = isRelevant ? 'var(--accent-purple)' : 'var(--border-color)';
              markerUrl = isRelevant ? 'url(#arrow-highlight)' : 'url(#arrow)';
              strokeWidth = isRelevant ? 2 : 1;
            } else if (selectedCatalystPath) {
              opacity = isHighlighted ? 0.95 : 0.1;
              strokeColor = isHighlighted ? 'var(--accent-cyan)' : 'var(--border-color)';
              markerUrl = isHighlighted ? 'url(#arrow-cyan)' : 'url(#arrow)';
              strokeWidth = isHighlighted ? 2 : 1;
            }

            return (
              <line
                key={idx}
                x1={fromPos.x} y1={fromPos.y} x2={toPos.x} y2={toPos.y}
                stroke={strokeColor}
                strokeWidth={strokeWidth * scale}
                strokeDasharray={edge.edgeType.includes('exposure') ? `${3 * scale},${3 * scale}` : 'none'}
                opacity={opacity}
                markerEnd={markerUrl}
              />
            );
          })}

          {/* Nodes */}
          {graphData.nodes.map((node) => {
            const pos = positions.get(node.nodeId);
            if (!pos) return null;
            
            const isHighlighted = selectedCatalystPath?.includes(node.name) || false;
            const nodeTicker = getTickerSymbol(node);
            
            const isActiveTickerNode = isFiltered && node.nodeType === 'ticker' && nodeTicker === activeTicker;
            const isClicked = isNodeClicked && node.nodeId === clickedNodeId;
            const isWatchlisted = node.nodeType === 'ticker' && nodeTicker && watchlist.includes(nodeTicker);

            // Highlight status
            let opacity = 1;
            let nodeColor = getNodeColor(node.nodeType, isClicked || isActiveTickerNode || isHighlighted);
            if (node.nodeType === 'ticker' && !isWatchlisted && !(isClicked || isActiveTickerNode || isHighlighted)) {
              nodeColor = 'var(--accent-purple-light)';
            }
            let textFill = 'var(--text-secondary)';
            let fontWeight = node.nodeType === 'ticker' ? (isWatchlisted ? 'bold' : 'normal') : 'normal';

            if (isNodeClicked) {
              const isRelevant = connectedNodes.has(node.nodeId);
              opacity = isRelevant ? 1 : 0.15;
              if (!isRelevant) nodeColor = 'rgba(255, 255, 255, 0.08)';
              textFill = isRelevant ? (isClicked ? 'var(--accent-purple)' : 'var(--text-primary)') : 'var(--text-muted)';
              if (isClicked) fontWeight = 'bold';
            } else if (isFiltered) {
              const isRelevant = relevantNodes.has(node.nodeId);
              opacity = isRelevant ? 1 : 0.15;
              if (!isRelevant) nodeColor = 'rgba(255, 255, 255, 0.08)';
              textFill = isRelevant ? (isActiveTickerNode ? 'var(--accent-purple)' : 'var(--text-primary)') : 'var(--text-muted)';
              if (isActiveTickerNode) fontWeight = 'bold';
            } else if (selectedCatalystPath) {
              const isPath = selectedCatalystPath.includes(node.name);
              opacity = isPath ? 1 : 0.35;
              textFill = isPath ? 'var(--accent-purple)' : 'var(--text-secondary)';
              if (isPath) fontWeight = 'bold';
            }

            const r = (node.nodeType === 'ticker' ? 6 : 4.5) * scale;
            const labelOffset = (node.nodeType === 'ticker' ? 8 : -8) * scale;
            const textAnchor = node.nodeType === 'ticker' ? 'start' : 'end';

            let strokeColor = isHighlighted || isClicked || isActiveTickerNode ? 'white' : 'transparent';
            let strokeWidth = scale * (isClicked || isActiveTickerNode ? 1.5 : 1);
            let strokeDasharray = 'none';

            if (node.nodeType === 'ticker' && !isWatchlisted) {
              strokeColor = 'var(--accent-purple)';
              strokeWidth = scale * (isClicked || isActiveTickerNode ? 2 : 1.25);
              strokeDasharray = `${2 * scale},${2 * scale}`;
            }

            return (
              <g 
                key={node.nodeId} 
                opacity={opacity} 
                style={{ cursor: 'pointer' }}
                onClick={(e) => {
                  e.stopPropagation();
                  setClickedNodeId(clickedNodeId === node.nodeId ? null : node.nodeId);
                }}
              >
                <circle
                  cx={pos.x} cy={pos.y} r={r * (isClicked || isActiveTickerNode ? 1.25 : 1)}
                  fill={nodeColor}
                  stroke={strokeColor} 
                  strokeWidth={strokeWidth}
                  strokeDasharray={strokeDasharray}
                />
                <text
                  x={pos.x + labelOffset} y={pos.y + 3 * scale}
                  fill={textFill}
                  fontSize={`${fontSize}px`}
                  fontWeight={fontWeight}
                  textAnchor={textAnchor}
                >
                  {nodeTicker ? `${node.name} (${nodeTicker})` : node.name}
                </text>
                <title>{`${node.name}${nodeTicker ? ` (${nodeTicker})` : ''} (${node.nodeType})\nQuery terms: ${node.queryTerms.join(', ')}`}</title>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Floating Canvas controls */}
      <div 
        style={{ 
          position: 'absolute', bottom: '1rem', right: '1rem', 
          display: 'flex', gap: '0.4rem', background: '#ffffff', 
          padding: '0.35rem', borderRadius: '8px', border: '1px solid var(--border-color)',
          boxShadow: 'var(--shadow-sm)', zIndex: 10
        }}
      >
        <button 
          onClick={handleZoomIn} 
          style={{ width: '28px', height: '28px', borderRadius: '6px', border: '1px solid var(--border-color)', background: '#ffffff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1rem', fontWeight: 'bold', color: 'var(--text-secondary)' }}
          title="Zoom In"
        >
          +
        </button>
        <button 
          onClick={handleZoomOut} 
          style={{ width: '28px', height: '28px', borderRadius: '6px', border: '1px solid var(--border-color)', background: '#ffffff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1rem', fontWeight: 'bold', color: 'var(--text-secondary)' }}
          title="Zoom Out"
        >
          -
        </button>
        <button 
          onClick={handleZoomReset} 
          style={{ padding: '0 0.5rem', height: '28px', borderRadius: '6px', border: '1px solid var(--border-color)', background: '#ffffff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.68rem', fontWeight: 'bold', color: 'var(--text-secondary)' }}
          title="Reset View"
        >
          Reset
        </button>
      </div>
    </div>
  );
}


