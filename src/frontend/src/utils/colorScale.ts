import * as d3 from 'd3';
import { NETWORK_COLORS } from '@/design-tokens/colors';

export function createNodeColorScale(colorBy: string) {
  if (colorBy === 'tier') {
    return (node: { tier: string }) =>
      node.tier === 'core' ? NETWORK_COLORS.core_bank : NETWORK_COLORS.periphery_bank;
  }
  if (colorBy === 'risk') {
    const scale = d3.scaleOrdinal()
      .domain(['normal', 'waspada', 'siaga', 'krisis'])
      .range(['#003366', '#FFFF00', '#FF69B4', '#FF0000']);
    return (node: { riskZone: string }) => scale(node.riskZone) as string;
  }
  if (colorBy === 'centrality' || colorBy === 'debtrank') {
    const scale = d3.scaleSequential(d3.interpolateYlOrRd).domain([0, 1]);
    return (node: { systemicImportance: number }) => scale(node.systemicImportance);
  }
  return () => NETWORK_COLORS.periphery_bank;
}

export function createNodeSizeScale(nodes: { degree?: number; systemicImportance?: number }[], sizeBy: string) {
  const values = nodes.map(n => (sizeBy === 'degree' ? n.degree ?? 0 : n.systemicImportance ?? 0));
  const [min, max] = d3.extent(values) as [number, number];
  return d3.scaleSqrt().domain([min || 0, max || 1]).range([6, 28]);
}

export function createEdgeWidthScale(edges: { weight: number }[]) {
  const weights = edges.map(e => e.weight);
  const [min, max] = d3.extent(weights) as [number, number];
  return d3.scaleLinear().domain([min || 0, max || 1]).range([0.5, 4]);
}
