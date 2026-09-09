// Loose typing shim for d3-force-3d. Each factory is typed as a generic
// call returning `any` so the legacy BiologicalGraph panel keeps building
// with its `.forceSimulation<GraphNode>()` and `.forceLink<A,B>()` calls.
declare module "d3-force-3d" {
  /* eslint-disable @typescript-eslint/no-explicit-any */
  type F = <A = any, B = any>(...args: any[]) => any;
  export const forceSimulation: F;
  export const forceLink: F;
  export const forceManyBody: F;
  export const forceCenter: F;
  export const forceCollide: F;
  export const forceRadial: F;
  export const forceX: F;
  export const forceY: F;
  export const forceZ: F;
  /* eslint-enable @typescript-eslint/no-explicit-any */
}
