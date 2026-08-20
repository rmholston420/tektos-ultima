/**
 * Tektos-Ultima v1 — Biological System Graph
 *
 * Living, breathing architecture visualization.
 * SSR-safe: only renders on client.
 * Supports 2D (force-directed) and 3D (orbital) views.
 */

"use client";

import React, { useEffect, useRef, useMemo, useCallback, useState } from "react";
import * as d3 from "d3";
import * as d3Force3d from "d3-force-3d";

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  name: string;
  category: string;
  rank: number;
  radius: number;
  z?: number;
}

interface GraphEdge extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode;
  target: string | GraphNode;
  strength: number;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphEdge[];
}

interface BiologicalGraphProps {
  data?: GraphData;
}

type ViewMode = "2d" | "3d";

const CATEGORY_COLORS: Record<string, { fill: string; glow: string; label: string }> = {
  core: { fill: "#3b82f6", glow: "rgba(59, 130, 246, 0.4)", label: "Core" },
  ai: { fill: "#8b5cf6", glow: "rgba(139, 92, 246, 0.4)", label: "AI/LLM" },
  memory: { fill: "#10b981", glow: "rgba(16, 185, 94, 0.4)", label: "Memory" },
  storage: { fill: "#f59e0b", glow: "rgba(245, 158, 11, 0.4)", label: "Storage" },
  network: { fill: "#06b6d4", glow: "rgba(6, 182, 212, 0.4)", label: "Network" },
  monitoring: { fill: "#ec4899", glow: "rgba(236, 72, 153, 0.4)", label: "Monitoring" },
  plugins: { fill: "#f97316", glow: "rgba(249, 115, 22, 0.4)", label: "Plugins" },
  tools: { fill: "#14b8a6", glow: "rgba(20, 184, 166, 0.4)", label: "Tools" },
};

function generateSampleData(): GraphData {
  return {
    nodes: [
      { id: "main", name: "Main", category: "core", rank: 0.95, radius: 28 },
      { id: "protocol", name: "Protocol", category: "core", rank: 0.85, radius: 24 },
      { id: "runtime", name: "Runtime", category: "core", rank: 0.90, radius: 26 },
      { id: "store", name: "Event Store", category: "storage", rank: 0.80, radius: 22 },
      { id: "llm", name: "LLM Bridge", category: "ai", rank: 0.92, radius: 26 },
      { id: "embedder", name: "Embedder", category: "ai", rank: 0.60, radius: 18 },
      { id: "routing", name: "Model Router", category: "ai", rank: 0.70, radius: 20 },
      { id: "redis_mem", name: "Redis", category: "memory", rank: 0.75, radius: 20 },
      { id: "postgres", name: "PostgreSQL", category: "memory", rank: 0.78, radius: 22 },
      { id: "neo4j", name: "Neo4j", category: "memory", rank: 0.72, radius: 20 },
      { id: "backup", name: "Backup", category: "memory", rank: 0.50, radius: 16 },
      { id: "searxng", name: "SearXNG", category: "plugins", rank: 0.65, radius: 18 },
      { id: "tavily", name: "Tavily", category: "plugins", rank: 0.55, radius: 16 },
      { id: "ddg", name: "DuckDuckGo", category: "plugins", rank: 0.50, radius: 15 },
      { id: "farfalle", name: "Farfalle", category: "plugins", rank: 0.60, radius: 17 },
      { id: "email", name: "Email", category: "network", rank: 0.58, radius: 16 },
      { id: "telegram", name: "Telegram", category: "network", rank: 0.62, radius: 17 },
      { id: "repograph", name: "Repograph", category: "tools", rank: 0.73, radius: 20 },
      { id: "git", name: "Git", category: "tools", rank: 0.68, radius: 19 },
      { id: "axioms", name: "Axioms", category: "tools", rank: 0.65, radius: 18 },
      { id: "self_mod", name: "Self-Mod", category: "tools", rank: 0.70, radius: 19 },
      { id: "telemetry", name: "Telemetry", category: "monitoring", rank: 0.67, radius: 19 },
      { id: "recovery", name: "Recovery", category: "monitoring", rank: 0.63, radius: 18 },
      { id: "debugger", name: "Debugger", category: "monitoring", rank: 0.58, radius: 16 },
    ],
    links: [
      { source: "main", target: "protocol", strength: 0.9 },
      { source: "main", target: "runtime", strength: 0.95 },
      { source: "main", target: "store", strength: 0.85 },
      { source: "runtime", target: "llm", strength: 0.9 },
      { source: "llm", target: "embedder", strength: 0.7 },
      { source: "llm", target: "routing", strength: 0.8 },
      { source: "store", target: "redis_mem", strength: 0.8 },
      { source: "store", target: "postgres", strength: 0.85 },
      { source: "store", target: "neo4j", strength: 0.75 },
      { source: "postgres", target: "backup", strength: 0.6 },
      { source: "llm", target: "searxng", strength: 0.7 },
      { source: "llm", target: "tavily", strength: 0.6 },
      { source: "llm", target: "ddg", strength: 0.5 },
      { source: "llm", target: "farfalle", strength: 0.7 },
      { source: "runtime", target: "telegram", strength: 0.8 },
      { source: "runtime", target: "email", strength: 0.65 },
      { source: "repograph", target: "main", strength: 0.75 },
      { source: "git", target: "self_mod", strength: 0.8 },
      { source: "axioms", target: "main", strength: 0.7 },
      { source: "self_mod", target: "runtime", strength: 0.7 },
      { source: "telemetry", target: "main", strength: 0.7 },
      { source: "recovery", target: "runtime", strength: 0.75 },
      { source: "debugger", target: "runtime", strength: 0.65 },
      { source: "repograph", target: "neo4j", strength: 0.6 },
      { source: "git", target: "store", strength: 0.55 },
      { source: "farfalle", target: "telemetry", strength: 0.5 },
      { source: "telegram", target: "telemetry", strength: 0.55 },
    ],
  };
}

// ─── 2D Force-Directed ────────────────────────────────────────────

function draw2D(
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
  container: HTMLDivElement,
  data: GraphData,
  hoveredNode: string | null,
  selectedCategory: string,
  setHoveredNode: (id: string | null) => void,
) {
  svg.selectAll("*").remove();

  const w = container.clientWidth || 800;
  const h = container.clientHeight || 600;
  svg.attr("viewBox", `0 0 ${w} ${h}`);

  const defs = svg.append("defs");

  // Glow filter
  const glowFilter = defs
    .append("filter")
    .attr("id", "glow")
    .attr("x", "-50%")
    .attr("y", "-50%")
    .attr("width", "200%")
    .attr("height", "200%");
  glowFilter
    .append("feGaussianBlur")
    .attr("stdDeviation", "4")
    .attr("result", "coloredBlur");
  const feMerge = glowFilter.append("feMerge");
  feMerge.append("feMergeNode").attr("in", "coloredBlur");
  feMerge.append("feMergeNode").attr("in", "SourceGraphic");

  // Node gradients
  data.nodes.forEach((node) => {
    const cat = CATEGORY_COLORS[node.category] || CATEGORY_COLORS.core;
    const grad = defs
      .append("radialGradient")
      .attr("id", `glow-${node.id}`)
      .attr("cx", "50%")
      .attr("cy", "50%")
      .attr("r", "50%");
    grad.append("stop").attr("offset", "0%").attr("stop-color", cat.fill).attr("stop-opacity", 0.8);
    grad.append("stop").attr("offset", "60%").attr("stop-color", cat.fill).attr("stop-opacity", 0.3);
    grad.append("stop").attr("offset", "100%").attr("stop-color", cat.fill).attr("stop-opacity", 0);
  });

  // Edge gradients
  data.links.forEach((link, i) => {
    const srcColor =
      CATEGORY_COLORS[data.nodes.find((n) => n.id === link.source)?.category || "core"]?.fill || "#3b82f6";
    const tgtColor =
      CATEGORY_COLORS[data.nodes.find((n) => n.id === link.target)?.category || "core"]?.fill || "#3b82f6";
    const grad = defs
      .append("linearGradient")
      .attr("id", `edge-flow-${i}`)
      .attr("gradientUnits", "userSpaceOnUse");
    grad.append("stop").attr("offset", "0%").attr("stop-color", srcColor).attr("stop-opacity", 0.6);
    grad.append("stop").attr("offset", "50%").attr("stop-color", "#ffffff").attr("stop-opacity", 0.9);
    grad.append("stop").attr("offset", "100%").attr("stop-color", tgtColor).attr("stop-opacity", 0.6);
  });

  // Force simulation
  const simulation = d3
    .forceSimulation<GraphNode>(data.nodes)
    .force("link", d3.forceLink<GraphNode, GraphEdge>(data.links).id((d: GraphNode) => d.id).distance((d: GraphEdge) => 120 - d.strength * 60))
    .force("charge", d3.forceManyBody().strength(-400))
    .force("center", d3.forceCenter(w / 2, h / 2))
    .force("collision", d3.forceCollide<GraphNode>().radius((d: GraphNode) => d.radius + 8))
    .alphaDecay(0.02);

  // Links
  const linkGroup = svg.append("g").attr("class", "links");
  const link = linkGroup
    .selectAll("path")
    .data(data.links)
    .join("path")
    .attr("fill", "none")
    .attr("stroke-width", (d: GraphEdge) => 1 + d.strength * 2)
    .attr("stroke-opacity", 0.4)
    .attr("stroke-linecap", "round")
    .style("mix-blend-mode", "screen");

  // Nodes
  const nodeGroup = svg.append("g").attr("class", "nodes");
  const node = nodeGroup
    .selectAll("g")
    .data(data.nodes)
    .join("g")
    .attr("cursor", "pointer")
    .on("mouseover", function (_event: MouseEvent, d: GraphNode) {
      setHoveredNode(d.id);
      d3.select(this).select(".outer").transition().duration(200).attr("r", d.radius + 4);
    })
    .on("mouseout", function (_event: MouseEvent, d: GraphNode) {
      setHoveredNode(null);
      d3.select(this).select(".outer").transition().duration(200).attr("r", d.radius);
    });

  node.append("circle").attr("class", "outer").attr("r", (d) => d.radius).attr("fill", (d) => `url(#glow-${d.id})`).attr("filter", "url(#glow)");

  node
    .append("circle")
    .attr("class", "core")
    .attr("r", (d) => d.radius * 0.7)
    .attr("fill", (d) => CATEGORY_COLORS[d.category]?.fill || "#3b82f6")
    .attr("stroke", "#0a0e17")
    .attr("stroke-width", 2);

  node
    .append("text")
    .attr("text-anchor", "middle")
    .attr("dy", (d) => d.radius + 14)
    .attr("fill", "#94a3b8")
    .attr("font-size", "10px")
    .attr("font-family", "Inter, system-ui, sans-serif")
    .text((d) => d.name);

  simulation.on("tick", () => {
    node.attr("transform", (d) => `translate(${d.x || 0}, ${d.y || 0})`);
    link.attr("d", (d) => {
      const s = d.source as unknown as GraphNode;
      const t = d.target as unknown as GraphNode;
      const dx = t.x! - s.x!;
      const dy = t.y! - s.y!;
      const dr = Math.sqrt(dx * dx + dy * dy) * 1.5;
      return `M${s.x},${s.y}A${dr},${dr} 0 0,1 ${t.x},${t.y}`;
    });
    link.attr("stroke", (_d, i) => `url(#edge-flow-${i})`);
  });

  // Breathing animation
  let time = 0;
  const animationId = requestAnimationFrame(function animate() {
    time += 0.01;
    node.select(".outer").attr("opacity", () => 0.3 + Math.sin(time * 2) * 0.2);
    link.attr("stroke-opacity", () => 0.3 + Math.sin(time * 3) * 0.2);
    requestAnimationFrame(animate);
  });

  return () => {
    simulation.stop();
    cancelAnimationFrame(animationId);
  };
}

// ─── 3D Orbital ───────────────────────────────────────────────────

function draw3D(
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
  container: HTMLDivElement,
  data: GraphData,
  hoveredNode: string | null,
  selectedCategory: string,
  setHoveredNode: (id: string | null) => void,
) {
  svg.selectAll("*").remove();

  const w = container.clientWidth || 800;
  const h = container.clientHeight || 600;
  svg.attr("viewBox", `0 0 ${w} ${h}`);

  const defs = svg.append("defs");

  // Glow filter
  const glowFilter = defs
    .append("filter")
    .attr("id", "glow3d")
    .attr("x", "-50%")
    .attr("y", "-50%")
    .attr("width", "200%")
    .attr("height", "200%");
  glowFilter.append("feGaussianBlur").attr("stdDeviation", "3").attr("result", "coloredBlur");
  const feMerge = glowFilter.append("feMerge");
  feMerge.append("feMergeNode").attr("in", "coloredBlur");
  feMerge.append("feMergeNode").attr("in", "SourceGraphic");

  // Node gradients
  data.nodes.forEach((node) => {
    const cat = CATEGORY_COLORS[node.category] || CATEGORY_COLORS.core;
    const grad = defs
      .append("radialGradient")
      .attr("id", `glow3d-${node.id}`)
      .attr("cx", "50%")
      .attr("cy", "50%")
      .attr("r", "50%");
    grad.append("stop").attr("offset", "0%").attr("stop-color", cat.fill).attr("stop-opacity", 0.9);
    grad.append("stop").attr("offset", "60%").attr("stop-color", cat.fill).attr("stop-opacity", 0.4);
    grad.append("stop").attr("offset", "100%").attr("stop-color", cat.fill).attr("stop-opacity", 0);
  });

  // 3D force simulation
  const simulation = d3Force3d.forceSimulation<GraphNode>(data.nodes)
    .force(
      "link",
      d3Force3d.forceLink<GraphNode, GraphEdge>(data.links).id((d: GraphNode) => d.id).distance((d: GraphEdge) => 100 - d.strength * 40),
    )
    .force("charge", d3Force3d.forceManyBody().strength(-300))
    .force("center", d3Force3d.forceCenter(0, 0, 0))
    .force("collision", d3Force3d.forceCollide<GraphNode>().radius((d: GraphNode) => d.radius + 4))
    .force("radial", d3Force3d.forceRadial((d: GraphNode) => d.rank * 120, 0, 0, 0).strength((d: GraphNode) => 0.08 * d.rank))
    .alphaDecay(0.015)
    .velocityDecay(0.4);

  // Projection
  const projection = d3
    .geoConicEqualArea()
    .rotate([90, 0, 0])
    .parallels([0, 0])
    .fitExtent([[40, 40], [w - 40, h - 40]], { type: "Sphere" })
    .scale(Math.min(w, h) * 0.45);

  const path = d3.geoPath(projection);

  // Sphere background
  svg
    .append("circle")
    .attr("cx", w / 2)
    .attr("cy", h / 2)
    .attr("r", Math.min(w, h) * 0.42)
    .attr("fill", "none")
    .attr("stroke", "rgba(255,255,255,0.06)")
    .attr("stroke-width", 1)
    .attr("stroke-dasharray", "4 8");

  // Equator ring
  svg
    .append("ellipse")
    .attr("cx", w / 2)
    .attr("cy", h / 2)
    .attr("rx", Math.min(w, h) * 0.42)
    .attr("ry", Math.min(w, h) * 0.12)
    .attr("fill", "none")
    .attr("stroke", "rgba(255,255,255,0.04)")
    .attr("stroke-width", 1);

  // Links
  const linkGroup = svg.append("g").attr("class", "links-3d");
  const link = linkGroup
    .selectAll("path")
    .data(data.links)
    .join("path")
    .attr("fill", "none")
    .attr("stroke", (d: GraphEdge) => {
      const srcColor = CATEGORY_COLORS[data.nodes.find((n) => n.id === d.source)?.category || "core"]?.fill || "#3b82f6";
      const tgtColor = CATEGORY_COLORS[data.nodes.find((n) => n.id === d.target)?.category || "core"]?.fill || "#3b82f6";
      return `url(#edge3d-${d.source}-${d.target})`;
    })
    .attr("stroke-width", (d: GraphEdge) => 1 + d.strength * 1.5)
    .attr("stroke-opacity", 0.25)
    .attr("stroke-linecap", "round");

  // Edge gradients
  data.links.forEach((link) => {
    const srcColor = CATEGORY_COLORS[data.nodes.find((n) => n.id === link.source)?.category || "core"]?.fill || "#3b82f6";
    const tgtColor = CATEGORY_COLORS[data.nodes.find((n) => n.id === link.target)?.category || "core"]?.fill || "#3b82f6";
    const grad = defs
      .append("linearGradient")
      .attr("id", `edge3d-${link.source}-${link.target}`)
      .attr("gradientUnits", "userSpaceOnUse");
    grad.append("stop").attr("offset", "0%").attr("stop-color", srcColor).attr("stop-opacity", 0.5);
    grad.append("stop").attr("offset", "100%").attr("stop-color", tgtColor).attr("stop-opacity", 0.5);
  });

  // Nodes
  const nodeGroup = svg.append("g").attr("class", "nodes-3d");
  const node = nodeGroup
    .selectAll("g")
    .data(data.nodes)
    .join("g")
    .attr("cursor", "pointer")
    .on("mouseover", function (_event: MouseEvent, d: GraphNode) {
      setHoveredNode(d.id);
      d3.select(this).select(".core-3d").transition().duration(200).attr("r", d.radius + 3);
    })
    .on("mouseout", function (_event: MouseEvent, d: GraphNode) {
      setHoveredNode(null);
      d3.select(this).select(".core-3d").transition().duration(200).attr("r", d.radius);
    });

  node
    .append("circle")
    .attr("class", "outer-3d")
    .attr("r", (d) => d.radius)
    .attr("fill", (d) => `url(#glow3d-${d.id})`)
    .attr("filter", "url(#glow3d)");

  node
    .append("circle")
    .attr("class", "core-3d")
    .attr("r", (d) => d.radius * 0.75)
    .attr("fill", (d) => CATEGORY_COLORS[d.category]?.fill || "#3b82f6")
    .attr("stroke", "#0a0e17")
    .attr("stroke-width", 2);

  // 3D depth label (small dot for depth)
  node
    .append("circle")
    .attr("class", "depth-dot")
    .attr("r", 2)
    .attr("fill", "#ffffff")
    .attr("opacity", 0.5);

  node
    .append("text")
    .attr("text-anchor", "middle")
    .attr("dy", (d) => d.radius + 14)
    .attr("fill", "#94a3b8")
    .attr("font-size", "10px")
    .attr("font-family", "Inter, system-ui, sans-serif")
    .text((d) => d.name);

  simulation.on("tick", () => {
    node.attr("transform", (d) => {
      const p = projection([d.x || 0, d.y || 0]);
      return p ? `translate(${p[0]}, ${p[1]})` : "";
    });

    // Sort by z-depth for painter's algorithm
    node.attr("z-index", (d) => (d.z || 0));

    link.attr("d", (d) => {
      const s = d.source as unknown as GraphNode;
      const t = d.target as unknown as GraphNode;
      const sp = projection([s.x || 0, s.y || 0]);
      const tp = projection([t.x || 0, t.y || 0]);
      if (!sp || !tp) return "";
      const dx = tp[0] - sp[0];
      const dy = tp[1] - sp[1];
      const dr = Math.sqrt(dx * dx + dy * dy) * 1.2;
      return `M${sp[0]},${sp[1]}A${dr},${dr} 0 0,1 ${tp[0]},${tp[1]}`;
    });
  });

  // Slow rotation
  let angle = 0;
  const animationId = requestAnimationFrame(function animate() {
    angle += 0.002;
    projection.rotate([90 + Math.sin(angle) * 15, 0, 0]);
    simulation.force("projection", projection);
    simulation.alpha(0.05).restart();
    requestAnimationFrame(animate);
  });

  return () => {
    simulation.stop();
    cancelAnimationFrame(animationId);
  };
}

// ─── Component ────────────────────────────────────────────────────

export function BiologicalGraph({ data: propData }: BiologicalGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const data = useMemo(() => propData || generateSampleData(), [propData]);
  const [isMounted, setIsMounted] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("2d");
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  // SSR guard
  useEffect(() => {
    setIsMounted(true);
  }, []);

  const drawGraph = useCallback(() => {
    if (!svgRef.current || !containerRef.current) return;
    const svg = d3.select(svgRef.current);

    if (viewMode === "2d") {
      return draw2D(svg, containerRef.current, data, hoveredNode, selectedCategory, setHoveredNode);
    } else {
      return draw3D(svg, containerRef.current, data, hoveredNode, selectedCategory, setHoveredNode);
    }
  }, [data, viewMode, hoveredNode, selectedCategory]);

  useEffect(() => {
    if (!isMounted) return;
    const cleanup = drawGraph();
    return () => cleanup?.();
  }, [isMounted, drawGraph]);

  if (!isMounted) return null;

  return (
    <div className="w-full h-[600px] relative rounded-2xl overflow-hidden bg-gradient-to-br from-bg-1/80 to-bg-2/80 border border-border/50">
      <div ref={containerRef} className="w-full h-full">
        <svg ref={svgRef} className="w-full h-full" />
      </div>

      {/* View mode toggle */}
      <div className="absolute top-4 left-4 flex items-center gap-1 bg-black/30 backdrop-blur-sm rounded-lg p-0.5 border border-white/10">
        <button
          onClick={() => setViewMode("2d")}
          className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
            viewMode === "2d" ? "bg-accent text-white shadow-sm" : "text-text-muted hover:text-text-secondary"
          }`}
        >
          2D
        </button>
        <button
          onClick={() => setViewMode("3d")}
          className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
            viewMode === "3d" ? "bg-accent text-white shadow-sm" : "text-text-muted hover:text-text-secondary"
          }`}
        >
          3D
        </button>
      </div>

      {/* Subsystem legend */}
      <div className="absolute bottom-4 left-4 flex flex-col gap-2">
        <div className="text-xs font-medium text-text-muted uppercase tracking-wider mb-1">Subsystems</div>
        {Object.entries(CATEGORY_COLORS).map(([cat, colors]) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(selectedCategory === cat ? "all" : cat)}
            className={`flex items-center gap-2 px-2 py-1 rounded-lg text-xs transition-all ${
              selectedCategory === cat ? "bg-white/10 text-text-primary" : "text-text-muted hover:text-text-secondary"
            }`}
          >
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: colors.fill }} />
            {colors.label}
          </button>
        ))}
      </div>

      {/* Hover tooltip */}
      {hoveredNode &&
        (() => {
          const node = data.nodes.find((n) => n.id === hoveredNode);
          return node ? (
            <div className="absolute top-4 right-4 panel max-w-xs">
              <div className="text-sm font-medium text-text-primary">{node.name}</div>
              <div className="text-xs text-text-muted mt-1">Category: {node.category}</div>
              <div className="text-xs text-text-muted">Complexity: {Math.round(node.rank * 100)}%</div>
            </div>
          ) : null;
        })()}
    </div>
  );
}
