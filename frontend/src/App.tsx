import React, { useState, useEffect } from 'react';
import { Play, RotateCcw, Plus, Search, ExternalLink, Network, Database, ShieldAlert, Cpu, Layers, Maximize2, X, RefreshCw, Menu, ChevronDown, ChevronUp, Clock, AlertCircle } from 'lucide-react';

interface Catalyst {
  label: string;
  relationshipType: 'direct' | 'indirect';
  eventType: string;
  possibleInfluence: 'positive' | 'negative' | 'mixed' | 'unclear';
  confidence: 'low' | 'medium' | 'high' | 'tentative';
  impactPath?: string[];
}

interface GuardrailMetadata {
  judgeStatus: 'passed' | 'regenerated_passed' | 'degraded' | 'skipped_empty' | 'skipped_no_llm_mock_mode' | 'not_run_synthesis_failed';
  judgeAttempts: number;
  judgeDefects: string[];
  regenerated: boolean;
  degraded: boolean;
}

interface TickerSummary {
  summaryId: string;
  ticker: string;
  summaryHeadline: string;
  situationSummary: string;
  mainCatalysts: Catalyst[];
  overallPossibleInfluence: 'positive' | 'negative' | 'mixed' | 'unclear';
  confidence: 'low' | 'medium' | 'high' | 'tentative';
  uncertainties: string[];
  watchItems: string[];
  sourceEventIds: string[];
  sourceArticleUrls: string[];
  complianceDisclaimer?: string;
  notFinancialAdvice: boolean;
  guardrailMetadata?: GuardrailMetadata;
}

interface EventEntry {
  eventId: string;
  eventType: string;
  headline: string;
  eventSummary: string;
  hardFacts: string[];
  possibleDirectionalPressure: 'positive' | 'negative' | 'mixed' | 'unclear';
  sourceArticleIds: string[];
  sourceUrl?: string;
  impactPath?: string[];
  reasonForRouting?: string;
  pathConfidence?: number;
}

interface TickerBucket {
  ticker: string;
  directEvents: EventEntry[];
  crossImpactEvents: EventEntry[];
  suppressedDuplicateCount: number;
}

interface RunResult {
  runId: string;
  iteration: number;
  watchlist: string[];
  articlesCount: number;
  eventsCount: number;
  routedCount: number;
  duplicateCounts: Record<string, number>;
  tickerSyntheses: Record<string, TickerSummary>;
  rawArticles: any[];
  canonicalEvents: any[];
  routedCandidates: any[];
  tickerBuckets: Record<string, TickerBucket>;
}

interface GraphNode {
  nodeId: string;
  nodeType: string;
  name: string;
  ticker?: string;
  queryTerms: string[];
}

interface GraphEdge {
  fromNodeId: string;
  toNodeId: string;
  edgeType: string;
  strength: string;
  confidence: number;
  notes?: string;
}

interface ExposureGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

type ExpansionStatus = Record<string, { ticker: string; status: string; error?: string; addedNodes?: number; addedEdges?: number; updatedAt?: string }>;

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

const getTickerSymbol = (node: GraphNode): string | undefined => {
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

function GraphView({ graphData, width, height, scale = 1, selectedCatalystPath, activeTicker, watchlist = [] }: {
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

export default function App() {
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [newTicker, setNewTicker] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [iteration, setIteration] = useState<number>(3);
  const [scenarioId, setScenarioId] = useState<string>('live');
  const [activeTicker, setActiveTicker] = useState<string>('dashboard');
  const [runResults, setRunResults] = useState<Record<number, RunResult | null>>({});
  const runResult = runResults[iteration] || null;
  const [graphData, setGraphData] = useState<ExposureGraph>({ nodes: [], edges: [] });
  const [ledgerEntries, setLedgerEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [phoenixStatus, setPhoenixStatus] = useState<any>({ running: false, dashboardUrl: '' });
  const [selectedCatalystPath, setSelectedCatalystPath] = useState<string[] | null>(null);
  const [memoryStatus, setMemoryStatus] = useState<any>(null);
  const [graphModalOpen, setGraphModalOpen] = useState(false);
  const [graphFilterTicker, setGraphFilterTicker] = useState<string | null>(null);
  const [graphStatus, setGraphStatus] = useState<ExpansionStatus>({});

  // Dashboard Tabs & Status Bar states
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [ledgerExpanded, setLedgerExpanded] = useState(false);
  const [activeDashTab, setActiveDashTab] = useState<'watchlist' | 'ledger'>('watchlist');
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [addTickerOpen, setAddTickerOpen] = useState(false);
  const [synthesisExpanded, setSynthesisExpanded] = useState(false);
  const [selectedBackgroundStory, setSelectedBackgroundStory] = useState<string | null>(null);
  const [summaryDetailExpanded, setSummaryDetailExpanded] = useState(false);


  // Time conversion helper
  const formatRelativeTime = (publishedAt: string): string => {
    if (!publishedAt) return '—';
    const pub = new Date(publishedAt).getTime();
    const now = scenarioId === 'live' ? Date.now() : new Date('2026-05-28T17:25:00Z').getTime();
    const diffMs = now - pub;
    const diffMins = Math.max(0, Math.floor(diffMs / 60000));
    
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${Math.floor(diffHours / 24)}d ago`;
  };

  const getEventDecision = (eventId: string): string => {
    if (!runResult || !runResult.routedCandidates) return 'new';
    const cand = runResult.routedCandidates.find(c => c.eventId === eventId && c.ticker === activeTicker);
    return cand?.ledgerDecision || 'new';
  };

  const getEventCatalystId = (eventId: string): string | null => {
    if (!runResult || !runResult.routedCandidates) return null;
    const cand = runResult.routedCandidates.find(c => c.eventId === eventId && c.ticker === activeTicker);
    return cand?.catalystId || null;
  };

  const getEventTimestamp = (sourceArticleIds: string[]): string | null => {
    if (!runResult || !runResult.rawArticles || !sourceArticleIds || sourceArticleIds.length === 0) return null;
    const art = runResult.rawArticles.find(a => sourceArticleIds.includes(a.articleId));
    return art?.publishedAt || null;
  };

  // Removed initial load; now handled by connection manager check below

  useEffect(() => {
    fetchLedger();
  }, [iteration]);

  // Poll expansion status while any ticker is pending/running, refreshing the graph as
  // edges land. The effect re-arms on each graphStatus change and stops once all settle.
  useEffect(() => {
    const active = Object.values(graphStatus).some(s => s.status === 'pending' || s.status === 'running');
    if (!active) return;
    const t = setTimeout(() => {
      fetchGraphStatus();
      fetchGraph();
    }, 2500);
    return () => clearTimeout(t);
  }, [graphStatus]);

  const fetchWatchlist = async () => {
    try {
      const res = await fetch('/api/watchlist');
      const data = await res.json();
      setWatchlist(data.tickers);
      if (data.tickers.length > 0 && !activeTicker) {
        setActiveTicker('dashboard');
      }
    } catch (e) {
      console.error('Error fetching watchlist', e);
    }
  };

  const fetchGraph = async () => {
    try {
      const res = await fetch('/api/graph');
      const data = await res.json();
      setGraphData(data);
    } catch (e) {
      console.error('Error fetching graph', e);
    }
  };

  const fetchGraphStatus = async () => {
    try {
      const res = await fetch('/api/graph/status');
      const data = await res.json();
      setGraphStatus(data.status || {});
    } catch (e) {
      console.error('Error fetching graph status', e);
    }
  };

  // Manually (re-)run the LLM exposure-graph expansion for a ticker.
  const triggerExpansion = async (ticker: string) => {
    try {
      const res = await fetch('/api/graph/expand', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, force: true })
      });
      const data = await res.json();
      setGraphStatus(data.expansionStatus || {});
    } catch (e) {
      console.error('Error triggering graph expansion', e);
    }
  };

  // Rebuild the whole graph for every watchlist ticker. reset=true restores the curated
  // seed first (dropping accumulated LLM additions); reset=false refreshes additively.
  const rebuildGraph = async (reset: boolean) => {
    if (reset && !confirm('Reset the exposure graph to its curated seed and re-expand every watchlist ticker? This discards all accumulated LLM-generated nodes/edges.')) return;
    try {
      const res = await fetch('/api/graph/rebuild', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reset })
      });
      const data = await res.json();
      setGraphStatus(data.expansionStatus || {});
      fetchGraph();
    } catch (e) {
      console.error('Error rebuilding graph', e);
    }
  };

  // Resolves the display status for a ticker: explicit status entry, else "ready" if a
  // node already exists in the graph (seeded), else "none".
  const graphStatusFor = (ticker: string): string => {
    const s = graphStatus[ticker]?.status;
    if (s) return s;
    return graphData.nodes.some(n => n.nodeId === `ticker_${ticker}`) ? 'ready' : 'none';
  };

  const fetchResults = async () => {
    try {
      const res = await fetch('/api/results');
      if (res.ok) {
        const data = await res.json();
        if (data) {
          const formatted: Record<number, RunResult> = {};
          Object.entries(data).forEach(([k, v]) => {
            formatted[Number(k)] = v as RunResult;
          });
          setRunResults(formatted);
        }
      }
    } catch (e) {
      console.error('Error fetching run results', e);
    }
  };

  const fetchLedger = async () => {
    try {
      const res = await fetch(`/api/ledger?iteration=${iteration}`);
      const data = await res.json();
      setLedgerEntries(data);
    } catch (e) {
      console.error('Error fetching ledger', e);
    }
  };

  const fetchPhoenixStatus = async () => {
    try {
      const res = await fetch('/api/phoenix-status');
      const data = await res.json();
      setPhoenixStatus(data);
    } catch (e) {
      console.error('Error fetching Phoenix status', e);
    }
  };

  const fetchMemoryStatus = async () => {
    try {
      const res = await fetch('/api/memory-status');
      const data = await res.json();
      setMemoryStatus(data);
    } catch (e) {
      console.error('Error fetching memory status', e);
    }
  };

  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'failed'>('connecting');
  const [retryCount, setRetryCount] = useState(0);

  const checkConnectionDirect = async (): Promise<boolean> => {
    try {
      const res = await fetch('/api/watchlist');
      if (res.ok) {
        const data = await res.json();
        setWatchlist(data.tickers);
        if (data.tickers.length > 0 && !activeTicker) {
          setActiveTicker('dashboard');
        }
        // Fetch all other data on successful connection
        fetchGraph();
        fetchGraphStatus();
        fetchResults();
        fetchPhoenixStatus();
        fetchMemoryStatus();
        setConnectionState('connected');
        return true;
      }
    } catch (e) {
      console.warn('Backend connection attempt failed:', e);
    }
    return false;
  };

  useEffect(() => {
    let intervalId: any;
    let elapsed = 0;

    const runCheck = async () => {
      const success = await checkConnectionDirect();
      if (!success) {
        intervalId = setInterval(async () => {
          elapsed += 10;
          if (elapsed >= 90) { // 1.5 minutes
            setConnectionState('failed');
            clearInterval(intervalId);
          } else {
            setRetryCount(c => c + 1);
            const ok = await checkConnectionDirect();
            if (ok) {
              clearInterval(intervalId);
            }
          }
        }, 10000);
      }
    };

    runCheck();

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

  const handleManualRetry = () => {
    setConnectionState('connecting');
    setRetryCount(0);
    let elapsed = 0;

    const runCheck = async () => {
      const success = await checkConnectionDirect();
      if (!success) {
        const intervalId = setInterval(async () => {
          elapsed += 10;
          if (elapsed >= 90) {
            setConnectionState('failed');
            clearInterval(intervalId);
          } else {
            setRetryCount(c => c + 1);
            const ok = await checkConnectionDirect();
            if (ok) {
              clearInterval(intervalId);
            }
          }
        }, 10000);
      }
    };

    runCheck();
  };

  const addTicker = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTicker) return;
    const cleanTicker = newTicker.trim().toUpperCase();
    if (watchlist.includes(cleanTicker)) {
      setNewTicker('');
      setActiveTicker(cleanTicker);
      setAddTickerOpen(false);
      return;
    }

    const updated = [...watchlist, cleanTicker];
    try {
      const res = await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers: updated })
      });
      const data = await res.json();
      setWatchlist(data.tickers);
      setNewTicker('');
      setAddTickerOpen(false);
      setActiveTicker(cleanTicker);
      // The add is immediate; graph expansion runs in the background. Seed the status
      // map so the polling effect starts and the UI shows "pending" right away.
      setGraphStatus(data.expansionStatus || {});
    } catch (e) {
      console.error('Error updating watchlist', e);
    }
  };

  const clearLedgerMemory = async () => {
    if (!confirm('Are you sure you want to clear the Catalyst Ledger memory for this iteration? This will reset all story updates.')) return;
    try {
      const res = await fetch(`/api/ledger/clear?iteration=${iteration}`, { method: 'POST' });
      await res.json();
      fetchLedger();
      alert('Ledger cleared successfully!');
    } catch (e) {
      console.error('Error clearing ledger', e);
    }
  };

  const runPipeline = async () => {
    setLoading(true);
    setSelectedCatalystPath(null);
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          iteration,
          scenario_id: scenarioId,
          simulated_now: scenarioId === 'live' ? new Date().toISOString() : '2026-05-28T17:25:00Z'
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Pipeline execution failed');
      }
      const data = await res.json();
      setRunResults(prev => ({
        ...prev,
        [iteration]: data
      }));
      fetchLedger();
      fetchGraph();
      fetchMemoryStatus();
    } catch (e: any) {
      alert(`Pipeline execution error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const getActiveSynthesis = (): TickerSummary | null => {
    if (!runResult || !runResult.tickerSyntheses) return null;
    return runResult.tickerSyntheses[activeTicker] || null;
  };

  const getActiveBucket = (): TickerBucket | null => {
    if (!runResult || !runResult.tickerBuckets) return null;
    return runResult.tickerBuckets[activeTicker] || null;
  };

  const getTickerCompanyName = (ticker: string): string => {
    const node = graphData.nodes.find(n => n.nodeType === 'ticker' && getTickerSymbol(n) === ticker);
    if (node) return node.name;
    return (
      ticker === 'AAPL' ? 'Apple Inc.' :
      ticker === 'MSFT' ? 'Microsoft Corp.' :
      ticker === 'NVDA' ? 'Nvidia Corp.' :
      ticker === 'TSM' ? 'TSMC' :
      ticker === 'DAL' ? 'Delta Air Lines' : 'Public Company'
    );
  };

  // Small status pill shown next to each watchlist ticker, reflecting graph expansion.
  const renderGraphStatusPill = (ticker: string) => {
    const status = graphStatusFor(ticker);
    const map: Record<string, { label: string; color: string }> = {
      pending: { label: 'graph: queued', color: 'var(--accent-orange)' },
      running: { label: 'graph: building…', color: 'var(--accent-orange)' },
      done: { label: 'graph: ready', color: 'var(--accent-green)' },
      ready: { label: 'graph: ready', color: 'var(--accent-green)' },
      skipped: { label: 'graph: ready', color: 'var(--accent-green)' },
      failed: { label: 'graph: failed', color: 'var(--accent-red)' },
      none: { label: 'graph: —', color: 'var(--text-muted)' },
    };
    const meta = map[status] || map.none;
    const spinning = status === 'pending' || status === 'running';
    return (
      <span style={{ fontSize: '0.6rem', color: meta.color, display: 'flex', alignItems: 'center', gap: '0.2rem' }} title={graphStatus[ticker]?.error || meta.label}>
        {spinning && <span className="spinner" style={{ width: '8px', height: '8px', borderWidth: '1.5px' }} />}
        {meta.label}
      </span>
    );
  };

  if (connectionState === 'connecting') {
    return (
      <div className="connection-overlay">
        <div className="glass connection-card">
          <div className="connection-glow" />
          <div className="pulse-loader">
            <Cpu className="pulse-icon" size={48} />
          </div>
          <h2>⚡ Connecting to Cross-Impact Engine</h2>
          <p className="connection-status">
            The backend server at <code>http://localhost:8000</code> is still loading or offline.
          </p>
          <div className="polling-indicator">
            <span className="dot-pulse" />
            <span>Retrying connection (Attempt {retryCount + 1})...</span>
          </div>
          <div className="progress-bar-container">
            <div className="progress-bar-fill" style={{ width: `${(retryCount / 9) * 100}%` }} />
          </div>
          <span className="connection-info">Polling will stop automatically after 1.5 minutes.</span>
        </div>
      </div>
    );
  }

  if (connectionState === 'failed') {
    return (
      <div className="connection-overlay">
        <div className="glass connection-card connection-failed-card">
          <div className="connection-failed-glow" />
          <AlertCircle className="failed-icon" size={48} />
          <h2>❌ Server Offline / Connection Failed</h2>
          <p className="connection-status">
            Unable to establish a connection to the backend server at <code>http://localhost:8000</code> after 1.5 minutes of polling.
          </p>
          <p className="connection-instructions">
            Please make sure that the backend FastAPI server is running (e.g. via <code>uvicorn backend.main:app --reload</code>).
          </p>
          <button className="btn-primary retry-btn" onClick={handleManualRetry}>
            <RotateCcw size={16} style={{ marginRight: '0.4rem' }} />
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`app-layout theme-iter-${iteration}`}>
      {/* TopNavBar */}
      <header className="main-app-header">
        {/* Top Tier: Main Header */}
        <div className="header-top-tier">
          <div className="header-left">
            <span className="app-brand-title">Cross-Impact Catalyst Briefings</span>
          </div>

          {/* Iteration Switcher */}
          <nav className="iteration-tabs-container">
            <button 
              className={`iteration-tab-item ${iteration === 1 ? 'active' : ''}`}
              onClick={() => {
                setIteration(1);
                setSelectedCatalystPath(null);
              }}
            >
              <span className="tab-title">Iteration 1</span>
              <span className="tab-subtitle">Direct News Only</span>
            </button>
            <button 
              className={`iteration-tab-item ${iteration === 2 ? 'active' : ''}`}
              onClick={() => {
                setIteration(2);
                setSelectedCatalystPath(null);
              }}
            >
              <span className="tab-title">Iteration 2</span>
              <span className="tab-subtitle">News + History</span>
            </button>
            <button 
              className={`iteration-tab-item ${iteration === 3 ? 'active' : ''}`}
              onClick={() => {
                setIteration(3);
                setSelectedCatalystPath(null);
              }}
            >
              <span className="tab-title">Iteration 3</span>
              <span className="tab-subtitle">Cross-Impact Graph</span>
            </button>
          </nav>

          <div className="header-right">
            {/* Phoenix Active Indicator */}
            <div className="header-status-item">
              <span className="status-indicator-dot green-pulse" />
              <span className="status-label">PHOENIX: <span className="status-value-active">ACTIVE</span></span>
              {phoenixStatus.running && phoenixStatus.dashboardUrl && (
                <a 
                  href={phoenixStatus.dashboardUrl}
                  target="_blank" 
                  rel="noreferrer"
                  className="status-link-purple"
                >
                  Phoenix Traces
                </a>
              )}
            </div>

            {/* Memory Engine Indicator */}
            <div 
              className="header-status-item engine-popover-trigger" 
              style={{ position: 'relative', cursor: 'pointer' }}
              onClick={() => setPopoverOpen(!popoverOpen)}
            >
              <Database size={14} style={{ color: 'var(--text-muted)' }} />
              <span className="status-label">Memory Engine: <span className="status-value-bold">Local embeddings</span></span>
              
              {popoverOpen && (
                <>
                  <div className="engine-popover-backdrop" onClick={(e) => { e.stopPropagation(); setPopoverOpen(false); }} />
                  <div className="engine-popover" onClick={(e) => e.stopPropagation()}>
                    <div className="engine-popover-header">
                      Embeddings Memory Engine
                    </div>
                    {memoryStatus ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.75rem', color: 'var(--text-primary)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span className="metric-label">Dedup Provider</span>
                          <span style={{
                            fontWeight: 700,
                            padding: '0.1rem 0.35rem',
                            borderRadius: '3px',
                            background: memoryStatus.isFallbackActive ? 'rgba(234, 88, 12, 0.12)' : 'rgba(87, 0, 225, 0.12)',
                            color: memoryStatus.isFallbackActive ? 'var(--accent-orange)' : 'var(--accent-purple)',
                            border: `1px solid ${memoryStatus.isFallbackActive ? 'rgba(234,88,12,0.3)' : 'rgba(87,0,225,0.3)'}`
                          }}>{memoryStatus.dedupProvider}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span className="metric-label">Extraction LLM</span>
                          <span style={{ color: 'var(--accent-green)', fontFamily: 'monospace' }}>{memoryStatus.llmExtractionModel}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span className="metric-label">Synthesis LLM</span>
                          <span style={{ color: 'var(--accent-purple)', fontFamily: 'monospace' }}>{memoryStatus.llmSynthesisModel}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span className="metric-label">Dedup Method</span>
                          <span>{memoryStatus.dedupModel}</span>
                        </div>
                        <div style={{ height: '1px', background: 'var(--border-color)', margin: '0.2rem 0' }} />
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span className="metric-label">Cosine Threshold</span>
                          <span style={{ color: 'var(--accent-purple)' }}>&ge; {memoryStatus.similarityThreshold}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span className="metric-label">Jaccard Threshold</span>
                          <span style={{ color: 'var(--accent-blue)' }}>&ge; {memoryStatus.jaccardFactThreshold}</span>
                        </div>
                        <div style={{ height: '1px', background: 'var(--border-color)', margin: '0.2rem 0' }} />
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span className="metric-label">Stories in Ledger</span>
                          <span>{memoryStatus.ledgerLiveEntries} / {memoryStatus.ledgerTotalEntries}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span className="metric-label">Vectors Stored</span>
                          <span style={{ color: 'var(--accent-green)' }}>{memoryStatus.ledgerEmbeddedEntries}</span>
                        </div>
                        {memoryStatus.isFallbackActive && (
                          <div style={{
                            marginTop: '0.35rem',
                            padding: '0.4rem 0.5rem',
                            background: 'rgba(234, 88, 12, 0.08)',
                            border: '1px solid rgba(234,88,12,0.25)',
                            borderRadius: '5px',
                            fontSize: '0.7rem',
                            color: 'var(--accent-orange)',
                            lineHeight: 1.4
                          }}>
                            ⚠ Local embedding model unavailable. Using deterministic lexical lexical cosine fallback.
                          </div>
                        )}
                      </div>
                    ) : (
                      <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1rem' }}>Loading engine status...</div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Secondary Tier: Action Bar */}
        <div className="header-bottom-tier">
          <div className="subheader-left">
            {/* Scenario Selector */}
            <div className="scenario-selector-wrapper-header">
              <span className="scenario-label-header">SOURCE:</span>
              <select 
                id="header-scenario-select"
                className="scenario-select-header" 
                value={scenarioId} 
                onChange={(e) => setScenarioId(e.target.value)}
              >
                <option value="live">Live Feeds (Finnhub + Currents)</option>
                <option value="direct_news">Replay Scenario 1: Direct Announcements</option>
                <option value="duplicate_news">Replay Scenario 2: Duplicate Articles</option>
                <option value="cross_impact">Replay Scenario 3: Untickered Geopolitical/Tech</option>
              </select>
            </div>

            {/* Reset Cache button (only if iteration > 1) */}
            {iteration > 1 && (
              <button 
                className="btn-reset-cache-header" 
                onClick={clearLedgerMemory} 
                title="Reset active story thread cache in Ledger"
              >
                <RotateCcw size={12} />
                <span>Reset Cache</span>
              </button>
            )}

            {/* Explore Graph button (only if iteration === 3) */}
            {iteration === 3 && (
              <button 
                className="btn-explore-graph-header" 
                onClick={() => {
                  setGraphFilterTicker(null);
                  setGraphModalOpen(true);
                }}
                title="Explore the entire Causal Exposure Graph"
              >
                <Network size={12} />
                <span>Explore Graph</span>
              </button>
            )}
          </div>

          <div className="subheader-right">
            <span className="last-updated-label">LAST UPDATED: <span className="last-updated-value">14:32 UTC</span></span>
            <div className="header-vertical-divider" style={{ height: '16px', background: 'var(--border-color)', width: '1px', margin: '0 0.5rem' }} />
            <div className="live-feed-indicator" style={{ marginRight: '0.5rem' }}>
              <span className="indicator-dot green-pulse" />
              <span className="indicator-text">LIVE FEED ACTIVE</span>
            </div>

            <button 
              className="btn-fetch-catalysts" 
              onClick={runPipeline} 
              disabled={loading || watchlist.length === 0}
            >
              {loading ? (
                <div className="spinner-white" />
              ) : (
                <RefreshCw size={14} style={{ marginRight: '0.4rem' }} />
              )}
              <span>Fetch Catalysts</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="workspace">
        
        {/* Left Sidebar - Watchlist */}
        {sidebarOpen && (
          <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />
        )}
        <aside className={`glass sidebar ${sidebarOpen ? 'open' : ''}`}>
          {/* Pinned Overview Dashboard Selector */}
          <button
              className={`glass glass-hover watchlist-dashboard-btn ${activeTicker === 'dashboard' ? 'active' : ''}`}
              onClick={() => {
                setActiveTicker('dashboard');
                setSelectedCatalystPath(null);
                setSidebarOpen(false);
              }}
            >
              <Layers size={14} style={{ color: 'var(--accent-purple)' }} />
              <span>Overview Dashboard</span>
          </button>

          <div className="watchlist-controls">
            <div>
              <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.2rem' }}>
                Watchlist Tickers
              </h2>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>Active Asset Impact</div>
            </div>
            
            <div className="watchlist-search">
              <Search size={14} />
              <input 
                type="search" 
                placeholder="Search tickers..." 
                className="watchlist-input" 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <button type="button" className="btn-secondary add-asset-btn" onClick={() => setAddTickerOpen(true)}>
              <Plus size={15} />
              <span>Add Asset</span>
            </button>
          </div>

          {/* Ticker List */}
          <div className="watchlist-list">
            {watchlist.map(ticker => {
              const companyName = getTickerCompanyName(ticker);
              const query = searchQuery.trim().toLowerCase();
              if (query && !ticker.toLowerCase().includes(query) && !companyName.toLowerCase().includes(query)) return null;
              const isActive = activeTicker === ticker;
              const tickerSynthesis = runResult?.tickerSyntheses?.[ticker];
              const influence = tickerSynthesis?.overallPossibleInfluence || 'unclear';
              const hasCatalysts = tickerSynthesis && tickerSynthesis.summaryHeadline !== "No new catalysts detected";

              return (
                <div 
                  key={ticker} 
                  className={`glass glass-hover watchlist-item ${isActive ? 'active' : ''}`}
                  onClick={() => {
                    setActiveTicker(ticker);
                    setSelectedCatalystPath(null);
                    setSidebarOpen(false);
                  }}
                >
                  <div className="watchlist-copy">
                    <div className="ticker-name">{ticker}</div>
                    <div className="company-name">
                      {companyName}
                    </div>
                  </div>
                  <div className="watchlist-meta">
                    {runResult && (
                      <span className={`badge ${hasCatalysts ? influence : 'unclear'}`} style={{ fontSize: '0.65rem' }}>
                        {hasCatalysts ? influence : 'no change'}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

        </aside>

        {/* Center Panel - Dashboard and Synthesized briefing */}
        <main className="main-content">
          


          {loading ? (
            <div className="glass loading-overlay" style={{ flex: 1 }}>
              <div className="spinner"></div>
              <h2>
                {iteration === 1 && "Executing LLM Direct News Workflow"}
                {iteration === 2 && "Executing LLM Memory Deduplication"}
                {iteration === 3 && "Executing LLM Catalyst Workflow Graph"}
              </h2>
              <p style={{ color: 'var(--text-secondary)' }}>
                {iteration === 1 && "Fetching direct articles and executing extraction + synthesis..."}
                {iteration === 2 && "Deduplicating articles using local vector memory ledger..."}
                {iteration === 3 && "Expanding search terms and routing untickered geopolitical shocks..."}
              </p>
            </div>
          ) : activeTicker === 'dashboard' ? (
            /* ==========================================================
               View A: WATCHLIST OVERVIEW DASHBOARD (2-COLUMN SPLIT)
               ========================================================== */
            <div className={`dashboard-split ${iteration === 1 ? 'single-col' : ''}`}>
              {/* Left Column: Watchlist Signals */}
              {(() => {
                const activeAlertTickers = watchlist.filter(t => {
                  const synth = runResult?.tickerSyntheses?.[t];
                  return synth && synth.summaryHeadline !== "No new catalysts detected";
                });
                const quietTickers = watchlist.filter(t => !activeAlertTickers.includes(t));

                return (
                  <div className="dashboard-signals">
                    {/* Active Alerts */}
                    <div className="active-alerts-section">
                      <h2 className="section-title">🚨 Active Shocks & Alerts</h2>
                      {watchlist.length === 0 ? (
                        <div className="glass" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                          <h3>Watchlist is empty</h3>
                          <p style={{ marginTop: '0.5rem' }}>Add tickers in the left sidebar to start monitoring signals.</p>
                        </div>
                      ) : activeAlertTickers.length === 0 ? (
                        <div className="glass" style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                          No active breaking news alerts. Monitor quiet watchlist below.
                        </div>
                      ) : (
                        <div className="dashboard-grid">
                          {activeAlertTickers.map(ticker => {
                            const tickerSynthesis = runResult?.tickerSyntheses?.[ticker];
                            const influence = tickerSynthesis?.overallPossibleInfluence || 'unclear';
                            const headline = tickerSynthesis?.summaryHeadline || 'No new catalysts detected';
                            
                            // Find relative time of the last catalyst
                            const bucket = runResult?.tickerBuckets?.[ticker];
                            const allEvents = [...(bucket?.directEvents || []), ...(bucket?.crossImpactEvents || [])];
                            
                            let timeStr = '';
                            if (allEvents.length > 0) {
                              const firstEvt = allEvents[0];
                              const ts = getEventTimestamp(firstEvt.sourceArticleIds);
                              if (ts) {
                                timeStr = formatRelativeTime(ts);
                              }
                            }

                            const influenceIcons = {
                              positive: '▲',
                              negative: '▼',
                              mixed: '◆',
                              unclear: '—'
                            };

                            return (
                              <div 
                                key={ticker} 
                                className={`dashboard-card active-alert-card glow-${influence}`}
                                onClick={() => setActiveTicker(ticker)}
                              >
                                <div className="dashboard-card-header">
                                  <div>
                                    <div className="dashboard-card-ticker">{ticker}</div>
                                    <div className="dashboard-card-company">
                                      {(() => {
                                        const node = graphData.nodes.find(n => n.nodeType === 'ticker' && getTickerSymbol(n) === ticker);
                                        return node ? node.name : 'Public Company';
                                      })()}
                                    </div>
                                  </div>
                                  
                                  <span className={`dashboard-card-signal-badge ${influence}`}>
                                    <span style={{ fontSize: '0.8rem', lineHeight: 1, marginRight: '0.15rem' }}>
                                      {influenceIcons[influence]}
                                    </span>
                                    <span>{influence}</span>
                                  </span>
                                </div>
                                
                                <div className="dashboard-card-headline">
                                  {headline}
                                </div>
                                
                                <div className="dashboard-card-footer">
                                  <span className="dashboard-card-time">
                                    <Clock size={11} style={{ marginRight: '0.25rem', verticalAlign: 'middle', display: 'inline' }} />
                                    {timeStr ? `Updated ${timeStr}` : 'No recent update'}
                                  </span>
                                  <span className="dashboard-card-action">
                                    View Briefing →
                                  </span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* Quiet Tickers */}
                    {quietTickers.length > 0 && (
                      <div className="quiet-watchlist-section">
                        <h2 className="section-title">⚪ Quiet Watchlist</h2>
                        <table className="quiet-watchlist-table">
                          <thead>
                            <tr>
                              <th>Ticker</th>
                              <th>Company Name</th>
                              <th>Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {quietTickers.map(ticker => {
                              const tickerSynthesis = runResult?.tickerSyntheses?.[ticker];
                              const influence = tickerSynthesis?.overallPossibleInfluence || 'unclear';
                              return (
                                <tr key={ticker} onClick={() => setActiveTicker(ticker)}>
                                  <td className="quiet-row-ticker">{ticker}</td>
                                  <td className="quiet-row-company">
                                    {(() => {
                                      const node = graphData.nodes.find(n => n.nodeType === 'ticker' && getTickerSymbol(n) === ticker);
                                      return node ? node.name : (
                                        ticker === 'AAPL' ? 'Apple Inc.' :
                                        ticker === 'MSFT' ? 'Microsoft Corp.' :
                                        ticker === 'NVDA' ? 'Nvidia Corp.' :
                                        ticker === 'TSM' ? 'TSMC' :
                                        ticker === 'DAL' ? 'Delta Air Lines' : 'Public Company'
                                      );
                                    })()}
                                  </td>
                                  <td>
                                    <span className="quiet-row-badge">
                                      {influence === 'unclear' ? 'no change' : influence}
                                    </span>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* Right Column: Global Active Story Ledger */}
              {iteration > 1 && (
                <div className="dashboard-ledger glass">
                  <div className="dashboard-ledger-header">
                    <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', margin: 0 }}>
                      <Database size={14} style={{ color: 'var(--accent-purple)' }} />
                      Active Story Ledger (Global)
                    </h2>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      {ledgerEntries.length} threads
                    </span>
                  </div>
                  <div className="dashboard-ledger-list">
                    {ledgerEntries.length > 0 ? (
                      ledgerEntries.map(entry => (
                        <div key={entry.catalystId} className="ledger-list-card">
                          <div className="ledger-card-header">
                            <span className="ledger-card-ticker">{entry.ticker}</span>
                            <span className="ledger-card-type">{entry.eventType}</span>
                          </div>
                          <div className="ledger-card-summary">{entry.canonicalSummary}</div>
                          <div className="ledger-card-footer">
                            <span>Facts: {entry.hardFactsSeen.length}</span>
                            <span>First seen: {formatRelativeTime(entry.firstSeenAt)}</span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="ledger-list-empty">
                        No active story threads in memory ledger.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* ==========================================================
               View B: TICKER DETAILS WORKSPACE
               ========================================================== */
            <>
              {(() => {
                const synthesis = getActiveSynthesis();
                const bucket = getActiveBucket();
                if (!synthesis) {
                  return (
                    <div className="glass" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)', flex: 1 }}>
                      <h2>No Active Run Data</h2>
                      <p style={{ marginTop: '0.5rem' }}>Select an iteration and news scenario, then click "Fetch Catalysts" to populate briefing cards.</p>
                    </div>
                  );
                }

                const influenceColor = synthesis.overallPossibleInfluence;
                const hasCatalysts = synthesis.summaryHeadline !== "No new catalysts detected";

                // Gather and filter supporting events
                const allEvents = [...bucket.directEvents, ...bucket.crossImpactEvents];
                
                // Filter out cross-impact events from feeds if iteration < 3
                const filteredAllEvents = iteration < 3 
                  ? allEvents.filter(e => !bucket.crossImpactEvents.find(c => c.eventId === e.eventId))
                  : allEvents;

                // Helper to get score for sorting
                const getCombinedScore = (evt: EventEntry) => {
                  const ts = getEventTimestamp(evt.sourceArticleIds);
                  const timeMs = ts ? new Date(ts).getTime() : 0;
                  const now = scenarioId === 'live' ? Date.now() : new Date('2026-05-28T17:25:00Z').getTime();
                  const ageMinutes = Math.max(0, (now - timeMs) / 60000);
                  
                  // Find significance from synthesis mainCatalysts
                  const catalystInfo = synthesis.mainCatalysts?.find((c: any) => c.eventId === evt.eventId);
                  const significance = catalystInfo ? (catalystInfo.significance || 5) : 3;
                  
                  return (significance * 10) - (ageMinutes * 0.5);
                };

                // Merge and sort events
                const sortedEvents = [...filteredAllEvents].sort((a, b) => getCombinedScore(b) - getCombinedScore(a));

                const activeTickerLedger = ledgerEntries.filter(l => l.ticker === activeTicker);

                return (
                  <div className="ticker-detail-split">
                    {/* Left Column: Ticker Synthesis Briefing */}
                    <div className="briefing-column">
                      
                      {/* FOCUS ASSET INFO CARD */}
                      <div className="glass focus-asset-info-card">
                        <div className="focus-asset-header-row">
                          <div>
                            <span className="focus-ticker-title">{activeTicker}</span>
                            <span className="focus-company-subtitle">{getTickerCompanyName(activeTicker)}</span>
                          </div>
                          <span className="focus-asset-badge">FOCUS ASSET</span>
                        </div>
                        
                        <div className="focus-metrics-row">
                          {/* Sentiment Card */}
                          <div className={`focus-metric-card sentiment-${influenceColor}`}>
                            <div className="focus-metric-title">SYNTHESIS SENTIMENT</div>
                            <div className="focus-metric-value-row">
                              <span className="focus-metric-value">
                                {hasCatalysts ? (
                                  influenceColor === 'positive' ? 'Bullish Bias' :
                                  influenceColor === 'negative' ? 'Bearish Bias' :
                                  influenceColor === 'mixed' ? 'Mixed Pressures' : 'Unclear Direction'
                                ) : 'No New Catalysts'}
                              </span>
                              <span className="focus-metric-icon">
                                {influenceColor === 'positive' && (
                                  <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941"></path>
                                  </svg>
                                )}
                                {influenceColor === 'negative' && (
                                  <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6L9 12.75l4.306-4.307a11.95 11.95 0 015.814 5.519l2.74 1.22m0 0l-5.94 2.28m5.94-2.28l-2.28-5.941"></path>
                                  </svg>
                                )}
                                {(influenceColor === 'mixed' || influenceColor === 'unclear') && (
                                  <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14"></path>
                                  </svg>
                                )}
                              </span>
                            </div>
                          </div>
                          
                          {/* Confidence Card */}
                          <div className="focus-metric-card confidence-purple">
                            <div className="focus-metric-title">MODEL CONFIDENCE</div>
                            <div className="focus-metric-value-row">
                              <span className="focus-metric-value">
                                {synthesis.confidence === 'high' ? 'High (88%)' :
                                 synthesis.confidence === 'medium' ? 'Medium (65%)' :
                                 synthesis.confidence === 'low' ? 'Low (42%)' : 'Tentative (30%)'}
                              </span>
                              <span className="focus-metric-icon">
                                <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0112 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.746 3.746 0 011.043 3.296A3.745 3.745 0 0121 12z"></path>
                                </svg>
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* View Causal Graph Button */}
                        {iteration === 3 && (
                          <div style={{ marginTop: '1rem' }}>
                            <button
                              onClick={() => {
                                setGraphFilterTicker(activeTicker);
                                setGraphModalOpen(true);
                              }}
                              className="btn-primary-purple"
                            >
                              <Network size={16} style={{ marginRight: '0.5rem' }} />
                              View Causal Graph
                            </button>
                          </div>
                        )}
                      </div>

                      {/* DETAILED BRIEFING CARD */}
                      <div className="glass synthesis-card briefing-detail-card">
                        <h2 className="briefing-headline">{synthesis.summaryHeadline}</h2>
                        
                        <div className="synthesis-summary briefing-summary-box">
                          {(() => {
                            const text = synthesis.situationSummary || "";
                            const sentences = text.match(/[^.!?]+[.!?]+(\s|$)/g) || [text];
                            if (sentences.length <= 2) {
                              return <span>{text}</span>;
                            }
                            const shortPart = sentences.slice(0, 2).join("").trim();
                            const restPart = sentences.slice(2).join("").trim();
                            
                            if (summaryDetailExpanded) {
                              return (
                                <span>
                                  {shortPart} {restPart}
                                  <span className="summary-toggle-link" onClick={() => setSummaryDetailExpanded(false)}>
                                    [Show Less]
                                  </span>
                                </span>
                              );
                            } else {
                              return (
                                <span>
                                  {shortPart}...
                                  <span className="summary-toggle-link" onClick={() => setSummaryDetailExpanded(true)}>
                                    [Show More]
                                  </span>
                                </span>
                              );
                            }
                          })()}
                        </div>

                        {/* Columns: Uncertainties & Watch Items */}
                        <div className="synthesis-details-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', marginTop: '1.25rem' }}>
                          <div className="details-column uncertainties-box">
                            <h3 className="uncertainties-title">
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '0.35rem' }}>
                                <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                                <line x1="12" y1="9" x2="12" y2="13"/>
                                <line x1="12" y1="17" x2="12.01" y2="17"/>
                              </svg>
                              Uncertainties / Open Risks
                            </h3>
                            <ul className="details-list">
                              {synthesis.uncertainties.map((u, i) => (
                                <li key={i} className="uncertainty-item">{u}</li>
                              ))}
                            </ul>
                          </div>

                          <div className="details-column watchitems-box">
                            <h3 className="watchitems-title">
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '0.35rem' }}>
                                <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0z"/>
                                <circle cx="12" cy="12" r="3"/>
                              </svg>
                              Trader Watchlist Items
                            </h3>
                            <ul className="details-list">
                              {synthesis.watchItems.map((wi, i) => (
                                <li key={i} className="watchitem-item">{wi}</li>
                              ))}
                            </ul>
                          </div>
                        </div>

                        {/* Compliance Disclaimer */}
                        <div className="compliance-disclaimer">
                          <ShieldAlert size={14} style={{ color: 'var(--accent-orange)', flexShrink: 0 }} />
                          <p style={{ fontSize: '0.75rem', margin: 0 }}>{synthesis.complianceDisclaimer || "Grounded information only. Not investment advice."}</p>
                        </div>
                      </div>
                    </div>

                    {/* Right Column: Unified Live Feed + Structured Memory Index */}
                    <div className="feed-column">
                      
                      {/* Unified Live Feed */}
                      <div className="catalysts-section">
                        <h3 className="feed-type-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <span className="pulsing-dot" style={{ color: iteration === 1 ? 'var(--accent-blue)' : iteration === 2 ? 'var(--accent-purple)' : 'var(--accent-cyan)' }} />
                            ⚡ Live Updates & Catalyst Feed
                          </span>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'none', fontWeight: 'normal' }}>
                            {sortedEvents.length} events sorted by recency & significance
                          </span>
                        </h3>

                        {sortedEvents.length > 0 ? (
                          <div className="catalysts-grid">
                            {sortedEvents.map((evt) => {
                              const isCross = bucket.crossImpactEvents.find(c => c.eventId === evt.eventId);
                              const isGraphHovered = selectedCatalystPath && selectedCatalystPath.join(',') === evt.impactPath?.join(',');
                              const ts = getEventTimestamp(evt.sourceArticleIds);
                              
                              const catId = getEventCatalystId(evt.eventId);
                              const elId = catId ? `evt-${catId}` : `evt-${evt.eventId}`;

                              const ledgerEntry = ledgerEntries.find(l => l.catalystId === catId);
                              
                              // Check decision: new vs update
                              const decision = iteration === 1 ? 'new' : getEventDecision(evt.eventId);
                              const isUpdate = decision === 'update';

                              // Find significance rating for badge
                              const catalystInfo = synthesis.mainCatalysts?.find((c: any) => c.eventId === evt.eventId);
                              const significance = catalystInfo ? (catalystInfo.significance || 5) : 3;

                              // Segment facts: new vs previous
                              const newFacts = evt.hardFacts;
                              const prevFacts = (isUpdate && ledgerEntry)
                                ? ledgerEntry.hardFactsSeen
                                    .map((f: any) => (typeof f === 'object' && f !== null) ? f.fact : String(f))
                                    .filter((factText: string) => !newFacts.includes(factText))
                                : [];

                              return (
                                <div 
                                  id={elId}
                                  key={evt.eventId} 
                                  className={`glass catalyst-card ${isUpdate ? 'ongoing-card' : `fresh-card accent-${iteration}`}`}
                                  style={isCross ? { 
                                    borderColor: isGraphHovered ? 'var(--accent-cyan)' : 'var(--border-color)',
                                    boxShadow: isGraphHovered ? '0 0 15px rgba(6, 182, 212, 0.15)' : 'none',
                                    transition: 'all 0.2s'
                                  } : {}}
                                  onMouseEnter={() => isCross && evt.impactPath && setSelectedCatalystPath(evt.impactPath)}
                                  onMouseLeave={() => isCross && setSelectedCatalystPath(null)}
                                >
                                  <div className="catalyst-card-header" style={{ paddingRight: '12rem' }}>
                                    <span className="badge" style={{ 
                                      borderColor: isCross ? 'rgba(6, 182, 212, 0.3)' : isUpdate ? 'rgba(255,255,255,0.1)' : 'rgba(168, 85, 247, 0.3)', 
                                      color: isCross ? 'var(--accent-cyan)' : isUpdate ? 'var(--text-secondary)' : 'var(--accent-purple)' 
                                    }}>
                                      {isCross 
                                        ? (isUpdate ? 'Ongoing Cross-Impact' : 'Cross-Impact Catalyst') 
                                        : (isUpdate ? 'Ongoing Direct Thread' : 'Direct Catalyst')}
                                    </span>
                                    <span className={`badge ${evt.possibleDirectionalPressure}`}>{evt.possibleDirectionalPressure}</span>
                                  </div>

                                  <div style={{ position: 'absolute', top: '1.25rem', right: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                    {/* Significance Badge */}
                                    <span className="badge" style={{
                                      background: significance >= 7 ? 'rgba(239, 68, 68, 0.12)' : 'rgba(255, 255, 255, 0.05)',
                                      color: significance >= 7 ? 'var(--accent-red)' : 'var(--text-secondary)',
                                      border: `1px solid ${significance >= 7 ? 'rgba(239, 68, 68, 0.25)' : 'var(--border-color)'}`,
                                      fontSize: '0.65rem',
                                      padding: '0.1rem 0.4rem',
                                      fontWeight: 800
                                    }}>
                                      Sig: {significance}/10
                                    </span>

                                    {/* Recency Badge */}
                                    <span className={isUpdate ? 'ongoing-badge' : 'fresh-badge'} style={{ position: 'static', margin: 0 }}>
                                      {!isUpdate && <span className="pulsing-dot" />}
                                      {ts ? formatRelativeTime(ts) : 'breaking'}
                                    </span>
                                  </div>

                                  <div className="catalyst-title" style={{ marginTop: '0.35rem' }}>{evt.headline}</div>
                                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                                    {evt.eventSummary}
                                  </p>

                                  {isUpdate ? (
                                    /* Story Timeline progression for Updates */
                                    <div className="storyline-timeline">
                                      <div className="timeline-title">Story Timeline & Fact Progression</div>
                                      <div className="timeline-facts-box">
                                        {/* New Facts */}
                                        {newFacts.map((fact, index) => (
                                          <div key={`new-${index}`} className="timeline-node new-fact">
                                            <span className="timeline-badge-new">NEW</span>
                                            {fact}
                                          </div>
                                        ))}
                                        
                                        {/* Previous Facts (Dimmed) */}
                                        {prevFacts.map((fact: string, index: number) => (
                                          <div key={`prev-${index}`} className="timeline-node" style={{ opacity: 0.55 }}>
                                            <span className="timeline-badge-priced-in">PRICED IN</span>
                                            {fact}
                                          </div>
                                        ))}
                                      </div>
                                      
                                      {ledgerEntry && (
                                        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', display: 'flex', gap: '1rem', marginTop: '0.25rem', paddingLeft: '0.75rem' }}>
                                          <span>First Seen: {formatRelativeTime(ledgerEntry.firstSeenAt)}</span>
                                          <span>Total reports: {ledgerEntry.memberArticleIds.length}</span>
                                        </div>
                                      )}
                                    </div>
                                  ) : (
                                    /* Hard facts for new news cards */
                                    <div className="catalyst-fact-box">
                                      <div className="fact-title">Hard Facts Grounded in Text:</div>
                                      {evt.hardFacts.map((fact, index) => (
                                        <div key={index} className="catalyst-fact">• {fact}</div>
                                      ))}
                                    </div>
                                  )}

                                  {isCross && evt.impactPath && (
                                    <div style={{ marginTop: '1rem' }}>
                                      <div className="fact-title" style={{ marginBottom: '0.25rem' }}>Exposure Chain Traversed:</div>
                                      <div className="impact-path-display">
                                        {evt.impactPath.map((step, idx) => {
                                          const isFirst = idx === 0;
                                          const isLast = idx === evt.impactPath!.length - 1;
                                          return (
                                            <React.Fragment key={idx}>
                                              <span className={`path-step ${isFirst ? 'source' : ''} ${isLast ? 'ticker' : ''}`}>
                                                {step}
                                              </span>
                                              {!isLast && <span className="path-arrow">→</span>}
                                            </React.Fragment>
                                          );
                                        })}
                                        {!isUpdate && (
                                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                                            Path Score: {evt.pathConfidence}
                                          </span>
                                        )}
                                      </div>
                                      {!isUpdate && evt.reasonForRouting && (
                                        <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.5rem', fontStyle: 'italic' }}>
                                          <strong>Causal path:</strong> {evt.reasonForRouting}
                                        </p>
                                      )}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="glass" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                            No catalysts detected in this run.
                          </div>
                        )}
                      </div>

                      {/* Active Memory Index (Database state - shown in Iterations 2 & 3) */}
                      {iteration > 1 && activeTickerLedger.length > 0 && (
                        <section className="glass panel-card">
                          <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', margin: 0 }}>
                            <Database size={13} style={{ color: 'var(--accent-purple)' }} />
                            Active Memory Index ({activeTickerLedger.length} stories in local DB)
                          </h2>
                          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                            Current state of local vector database memory. Click active updates to scroll to card, or background entries to expand hard facts inline.
                          </p>
                          <div className="memory-index-scroll">
                            {activeTickerLedger.map((entry) => {
                              const isUpdatedInRun = sortedEvents.some(e => getEventCatalystId(e.eventId) === entry.catalystId);
                              const isSelected = selectedBackgroundStory === entry.catalystId;
                              
                              return (
                                <div 
                                  key={entry.catalystId} 
                                  className={`memory-index-row ${isUpdatedInRun ? 'status-active' : 'status-background'}`}
                                  onClick={() => {
                                    if (isUpdatedInRun) {
                                      const el = document.getElementById(`evt-${entry.catalystId}`);
                                      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                    } else {
                                      setSelectedBackgroundStory(isSelected ? null : entry.catalystId);
                                    }
                                  }}
                                >
                                  <div className="index-row-header">
                                    <span className="index-row-type">{entry.eventType}</span>
                                    <span className={`index-row-status-dot ${isUpdatedInRun ? 'active' : 'background'}`} />
                                  </div>
                                  <div className="index-row-title">{entry.canonicalSummary}</div>
                                  <div className="index-row-footer">
                                    <span>First seen: {formatRelativeTime(entry.firstSeenAt)}</span>
                                    <span>Facts: {entry.hardFactsSeen.length}</span>
                                  </div>

                                  {!isUpdatedInRun && isSelected && (
                                    <div className="index-row-expanded" onClick={(e) => e.stopPropagation()}>
                                      <div className="expanded-summary-title">Full Grounded Memory State:</div>
                                      <div className="expanded-facts-list">
                                        {entry.hardFactsSeen.map((factObj: any, idx: number) => {
                                          const factText = (typeof factObj === 'object' && factObj !== null) ? factObj.fact : String(factObj);
                                          return (
                                            <div key={idx} className="expanded-fact-item">• {factText}</div>
                                          );
                                        })}
                                      </div>
                                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                                        First seen: {formatRelativeTime(entry.firstSeenAt)} | Reports: {entry.memberArticleIds.length}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </section>
                      )}
                    </div>
                  </div>
                );
              })()}
            </>
          )}
        </main>
      </div>

      {addTickerOpen && (
        <div className="modal-backdrop" onClick={() => setAddTickerOpen(false)}>
          <form className="glass add-ticker-modal" onSubmit={addTicker} onClick={(e) => e.stopPropagation()}>
            <div className="add-ticker-header">
              <div>
                <h2>Add Asset</h2>
                <p>Add a ticker to the active watchlist.</p>
              </div>
              <button type="button" className="icon-btn" onClick={() => setAddTickerOpen(false)} aria-label="Close add asset dialog">
                <X size={16} />
              </button>
            </div>
            <input
              autoFocus
              type="text"
              placeholder="Ticker symbol, e.g. MSFT"
              className="watchlist-input add-ticker-input"
              value={newTicker}
              onChange={(e) => setNewTicker(e.target.value)}
            />
            <div className="add-ticker-actions">
              <button type="button" className="btn-secondary" onClick={() => setAddTickerOpen(false)}>
                Cancel
              </button>
              <button type="submit" className="btn-primary" disabled={!newTicker.trim()}>
                <Plus size={15} />
                <span>Add Asset</span>
              </button>
            </div>
          </form>
        </div>
      )}



      {/* Full-screen Exposure Graph Modal */}
      {graphModalOpen && (
        <div className="graph-modal-backdrop" onClick={() => setGraphModalOpen(false)}>
          <div className="graph-modal-content" onClick={(e) => e.stopPropagation()}>
            {/* Modal header */}
            <div className="graph-modal-header">
              <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', margin: 0 }}>
                <Network size={18} /> Causal Exposure Graph
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 400 }}>
                  {graphData.nodes.length} nodes · {graphData.edges.length} edges
                </span>
              </h2>
              <button onClick={() => setGraphModalOpen(false)} className="btn-secondary" style={{ padding: '0.35rem 0.6rem', display: 'flex', alignItems: 'center', gap: '0.3rem', height: '30px' }}>
                <X size={14} /> Close
              </button>
            </div>

            <div className="graph-modal-body">
              {/* Large graph canvas */}
              <div className="graph-canvas-wrapper">
                <GraphView graphData={graphData} width={900} height={620} scale={2.2} selectedCatalystPath={selectedCatalystPath} activeTicker={graphFilterTicker || 'dashboard'} watchlist={watchlist} />
              </div>

              {/* Side rail: legend + per-ticker expansion controls */}
              <div className="graph-sidebar-rail">
                <div className="legend-section">
                  <h3 className="section-title" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Legend</h3>
                  
                  <div className="legend-item">
                    <span className="legend-color-dot" style={{ background: 'var(--accent-purple)' }} />
                    Ticker (watchlist)
                  </div>
                  
                  <div className="legend-item">
                    <span 
                      className="legend-color-dot" 
                      style={{ 
                        background: 'var(--accent-purple-light)', 
                        border: '1.25px dashed var(--accent-purple)',
                        boxSizing: 'border-box'
                      }} 
                    />
                    Ticker (derived)
                  </div>

                  <div className="legend-item">
                    <span className="legend-color-dot" style={{ background: 'var(--accent-blue)' }} />
                    Technology theme
                  </div>

                  <div className="legend-item">
                    <span className="legend-color-dot" style={{ background: 'var(--accent-cyan)' }} />
                    Company / sector
                  </div>

                  <div className="legend-item">
                    <span className="legend-color-dot" style={{ background: 'var(--accent-orange)' }} />
                    Region / risk / commodity / route
                  </div>

                  <div style={{ fontSize: '0.66rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                    Dashed edges = exposure links · solid = supplier/competitor/partner. Flow runs left → right into the ticker.
                  </div>
                </div>

                <div style={{ height: '1px', background: 'var(--border-color)', margin: '0.5rem 0' }} />

                <div>
                  <h3 className="section-title" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Global Rebuild</h3>
                  {(() => {
                    const anyBusy = watchlist.some(t => ['pending', 'running'].includes(graphStatusFor(t)));
                    return (
                      <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.75rem' }}>
                        <button
                          onClick={() => rebuildGraph(true)}
                          disabled={anyBusy}
                          className="btn-secondary"
                          style={{ flex: 1, padding: '0.35rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem', fontSize: '0.7rem', opacity: anyBusy ? 0.5 : 1, height: '30px' }}
                          title="Reset to curated seed, then re-expand every watchlist ticker"
                        >
                          <RotateCcw size={12} /> From seed
                        </button>
                        <button
                          onClick={() => rebuildGraph(false)}
                          disabled={anyBusy}
                          className="btn-secondary"
                          style={{ flex: 1, padding: '0.35rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem', fontSize: '0.7rem', opacity: anyBusy ? 0.5 : 1, height: '30px' }}
                          title="Force a fresh expansion for every watchlist ticker on top of the current graph"
                        >
                          <RefreshCw size={12} /> Refresh all
                        </button>
                      </div>
                    );
                  })()}

                  <h3 className="section-title" style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>Per-Ticker</h3>
                  {watchlist.map(ticker => {
                    const status = graphStatusFor(ticker);
                    const busy = status === 'pending' || status === 'running';
                    return (
                      <div key={ticker} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.4rem', padding: '0.35rem 0', borderBottom: '1px solid var(--border-color)' }}>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontWeight: 700, fontSize: '0.8rem' }}>{ticker}</span>
                          {renderGraphStatusPill(ticker)}
                        </div>
                        <button
                          onClick={() => triggerExpansion(ticker)}
                          disabled={busy}
                          className="btn-secondary"
                          style={{ padding: '0.25rem 0.5rem', display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.7rem', opacity: busy ? 0.5 : 1, height: '28px' }}
                          title="Re-run the LLM exposure-graph update for this ticker"
                        >
                          <RefreshCw size={12} /> Update
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
