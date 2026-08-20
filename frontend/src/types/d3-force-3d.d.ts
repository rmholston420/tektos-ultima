declare module 'd3-force-3d' {
  import { Simulation, SimulationNodeDatum, SimulationLinkDatum, ForceLink, ForceManyBody, ForceCenter, ForceCollide, ForceRadial, Force } from 'd3';

  export function forceSimulation<Node extends SimulationNodeDatum>(nodes: Node[]): Simulation<Node, SimulationLinkDatum<Node>>;
  export function forceLink<Node extends SimulationNodeDatum, Link extends SimulationLinkDatum<Node>>(links?: Link[]): ForceLink<Node, Link>;
  export function forceManyBody(): ForceManyBody<SimulationNodeDatum>;
  export function forceCenter(x?: number, y?: number, z?: number): ForceCenter<SimulationNodeDatum>;
  export function forceCollide<Node extends SimulationNodeDatum>(radius?: number | ((d: Node) => number)): ForceCollide<Node>;
  export function forceRadial<Node extends SimulationNodeDatum>(radius: number | ((d: Node) => number), x: number, y: number, z: number): ForceRadial<Node>;
}
