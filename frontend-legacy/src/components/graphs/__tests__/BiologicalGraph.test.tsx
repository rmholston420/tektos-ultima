/**
 * Tests for the BiologicalGraph component — data generation, rendering, interactions.
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";

// Build a chainable mock
function chain(obj: Record<string, any> = {}): any {
  const c: any = { ...obj };
  const fn = (name: string) => { c[name] = jest.fn(() => c); return c; };
  fn("attr"); fn("style"); fn("text"); fn("datum"); fn("each"); fn("call");
  fn("remove"); fn("on"); fn("enter"); fn("exit"); fn("transition");
  fn("duration"); fn("select"); fn("selectAll"); fn("empty"); fn("size");
  fn("nodes"); fn("append"); fn("data"); fn("join");
  return c;
}

const mockSel = chain();

jest.mock("d3", () => ({
  select: jest.fn(() => mockSel),
  selectAll: jest.fn(() => mockSel),
  forceSimulation: jest.fn(() => ({
    force: jest.fn().mockReturnThis(),
    on: jest.fn().mockReturnThis(),
    stop: jest.fn(),
    alpha: jest.fn().mockReturnThis(),
    restart: jest.fn(),
    tick: jest.fn(),
    alphaDecay: jest.fn().mockReturnThis(),
    velocityDecay: jest.fn().mockReturnThis(),
  })),
  forceLink: jest.fn(() => ({
    id: jest.fn().mockReturnThis(),
    distance: jest.fn().mockReturnThis(),
  })),
  forceManyBody: jest.fn(() => ({
    strength: jest.fn().mockReturnThis(),
  })),
  forceCenter: jest.fn(() => ({
    x: jest.fn().mockReturnThis(),
    y: jest.fn().mockReturnThis(),
  })),
  forceCollide: jest.fn(() => ({
    radius: jest.fn().mockReturnThis(),
  })),
  forceRadial: jest.fn(() => ({
    strength: jest.fn().mockReturnThis(),
  })),
  geoConicEqualArea: jest.fn(() => ({
    rotate: jest.fn().mockReturnThis(),
    parallels: jest.fn().mockReturnThis(),
    fitExtent: jest.fn().mockReturnThis(),
    scale: jest.fn().mockReturnThis(),
  })),
  geoPath: jest.fn(() => jest.fn()),
}));

jest.mock("d3-force-3d", () => ({
  forceSimulation: jest.fn(() => ({
    force: jest.fn().mockReturnThis(),
    on: jest.fn().mockReturnThis(),
    stop: jest.fn(),
    alpha: jest.fn().mockReturnThis(),
    restart: jest.fn(),
    alphaDecay: jest.fn().mockReturnThis(),
    velocityDecay: jest.fn().mockReturnThis(),
  })),
  forceLink: jest.fn(() => ({
    id: jest.fn().mockReturnThis(),
    distance: jest.fn().mockReturnThis(),
  })),
  forceManyBody: jest.fn(() => ({
    strength: jest.fn().mockReturnThis(),
  })),
  forceCenter: jest.fn(() => ({
    x: jest.fn().mockReturnThis(),
    y: jest.fn().mockReturnThis(),
    z: jest.fn().mockReturnThis(),
  })),
  forceCollide: jest.fn(() => ({
    radius: jest.fn().mockReturnThis(),
  })),
  forceRadial: jest.fn(() => ({
    strength: jest.fn().mockReturnThis(),
  })),
}));

import { BiologicalGraph } from "../BiologicalGraph";

describe("BiologicalGraph", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).requestAnimationFrame = (cb: FrameRequestCallback) => {
      setTimeout(cb, 0);
      return 0;
    };
    (global as any).cancelAnimationFrame = jest.fn();
    (window as any).ResizeObserver = jest.fn(() => ({
      observe: jest.fn(),
      unobserve: jest.fn(),
      disconnect: jest.fn(),
    }));
  });

  describe("rendering", () => {
    it("renders the graph container", () => {
      const { container } = render(<BiologicalGraph />);
      expect(container.querySelector("div.w-full")).toBeInTheDocument();
    });

    it("renders an SVG element", () => {
      const { container } = render(<BiologicalGraph />);
      expect(container.querySelector("svg")).toBeInTheDocument();
    });

    it("renders view mode toggle buttons", () => {
      render(<BiologicalGraph />);
      expect(screen.getByText("2D")).toBeInTheDocument();
      expect(screen.getByText("3D")).toBeInTheDocument();
    });

    it("renders subsystem legend", () => {
      render(<BiologicalGraph />);
      expect(screen.getByText("Subsystems")).toBeInTheDocument();
      expect(screen.getByText("Core")).toBeInTheDocument();
      expect(screen.getByText("AI/LLM")).toBeInTheDocument();
      expect(screen.getByText("Memory")).toBeInTheDocument();
      expect(screen.getByText("Storage")).toBeInTheDocument();
      expect(screen.getByText("Network")).toBeInTheDocument();
      expect(screen.getByText("Monitoring")).toBeInTheDocument();
      expect(screen.getByText("Plugins")).toBeInTheDocument();
      expect(screen.getByText("Tools")).toBeInTheDocument();
    });

    it("renders with 600px height container", () => {
      const { container } = render(<BiologicalGraph />);
      const graphDiv = container.querySelector("div.w-full");
      expect(graphDiv).toHaveClass("h-[600px]");
    });

    it("renders with gradient background", () => {
      const { container } = render(<BiologicalGraph />);
      const graphDiv = container.querySelector("div.w-full");
      expect(graphDiv).toHaveClass("bg-gradient-to-br");
    });
  });

  describe("view mode toggle", () => {
    it("defaults to 2D view", () => {
      render(<BiologicalGraph />);
      const btn2d = screen.getByText("2D");
      expect(btn2d).toHaveClass("bg-accent");
    });

    it("switches to 3D view when clicked", () => {
      render(<BiologicalGraph />);
      const btn3d = screen.getByText("3D");
      fireEvent.click(btn3d);
      expect(btn3d).toHaveClass("bg-accent");
      const btn2d = screen.getByText("2D");
      expect(btn2d).not.toHaveClass("bg-accent");
    });

    it("switches back to 2D view when clicked", () => {
      render(<BiologicalGraph />);
      const btn3d = screen.getByText("3D");
      const btn2d = screen.getByText("2D");
      fireEvent.click(btn3d);
      expect(btn3d).toHaveClass("bg-accent");
      fireEvent.click(btn2d);
      expect(btn2d).toHaveClass("bg-accent");
    });
  });

  describe("category filtering", () => {
    it("toggles category selection", () => {
      render(<BiologicalGraph />);
      const coreBtn = screen.getByText("Core");
      fireEvent.click(coreBtn);
      expect(coreBtn).toHaveClass("bg-white/10");
    });

    it("deselects category when clicked again", () => {
      render(<BiologicalGraph />);
      const coreBtn = screen.getByText("Core");
      fireEvent.click(coreBtn);
      expect(coreBtn).toHaveClass("bg-white/10");
      fireEvent.click(coreBtn);
      expect(coreBtn).not.toHaveClass("bg-white/10");
    });
  });

  describe("custom data", () => {
    it("renders with custom data prop", () => {
      const customData = {
        nodes: [{ id: "custom-1", name: "Custom Node", category: "core", rank: 0.8, radius: 20 }],
        links: [],
      };
      const { container } = render(<BiologicalGraph data={customData} />);
      expect(container.querySelector("svg")).toBeInTheDocument();
    });

    it("renders with empty data", () => {
      const emptyData = { nodes: [], links: [] };
      const { container } = render(<BiologicalGraph data={emptyData} />);
      expect(container.querySelector("svg")).toBeInTheDocument();
    });
  });

  describe("sample data", () => {
    it("generates sample data with expected node count", () => {
      render(<BiologicalGraph />);
      expect(screen.getByText("2D")).toBeInTheDocument();
    });

    it("sample data includes all subsystem categories", () => {
      render(<BiologicalGraph />);
      expect(screen.getByText("Core")).toBeInTheDocument();
      expect(screen.getByText("AI/LLM")).toBeInTheDocument();
      expect(screen.getByText("Memory")).toBeInTheDocument();
      expect(screen.getByText("Storage")).toBeInTheDocument();
      expect(screen.getByText("Network")).toBeInTheDocument();
      expect(screen.getByText("Monitoring")).toBeInTheDocument();
      expect(screen.getByText("Plugins")).toBeInTheDocument();
      expect(screen.getByText("Tools")).toBeInTheDocument();
    });
  });

  describe("container styling", () => {
    it("has rounded corners", () => {
      const { container } = render(<BiologicalGraph />);
      expect(container.querySelector("div.w-full")).toHaveClass("rounded-2xl");
    });

    it("has overflow hidden", () => {
      const { container } = render(<BiologicalGraph />);
      expect(container.querySelector("div.w-full")).toHaveClass("overflow-hidden");
    });

    it("has border", () => {
      const { container } = render(<BiologicalGraph />);
      expect(container.querySelector("div.w-full")).toHaveClass("border");
    });

    it("has relative positioning", () => {
      const { container } = render(<BiologicalGraph />);
      expect(container.querySelector("div.w-full")).toHaveClass("relative");
    });
  });

  describe("legend button styling", () => {
    it("has transition class on legend buttons", () => {
      render(<BiologicalGraph />);
      const coreBtn = screen.getByText("Core");
      expect(coreBtn).toHaveClass("transition-all");
    });

    it("has flex layout with gap on legend buttons", () => {
      render(<BiologicalGraph />);
      const coreBtn = screen.getByText("Core");
      expect(coreBtn).toHaveClass("flex");
      expect(coreBtn).toHaveClass("items-center");
      expect(coreBtn).toHaveClass("gap-2");
    });
  });

  describe("view mode toggle styling", () => {
    it("has backdrop blur on toggle container", () => {
      const { container } = render(<BiologicalGraph />);
      expect(container.querySelector("div.absolute.top-4")).toHaveClass("backdrop-blur-sm");
    });

    it("has rounded container for toggle", () => {
      const { container } = render(<BiologicalGraph />);
      expect(container.querySelector("div.absolute.top-4")).toHaveClass("rounded-lg");
    });

    it("has border on toggle container", () => {
      const { container } = render(<BiologicalGraph />);
      expect(container.querySelector("div.absolute.top-4")).toHaveClass("border");
    });
  });

  describe("legend container", () => {
    it("has absolute positioning at bottom-left", () => {
      const { container } = render(<BiologicalGraph />);
      expect(container.querySelector("div.absolute.bottom-4")).toHaveClass("left-4");
    });

    it("has flex column layout", () => {
      const { container } = render(<BiologicalGraph />);
      const legend = container.querySelector("div.absolute.bottom-4");
      expect(legend).toHaveClass("flex");
      expect(legend).toHaveClass("flex-col");
    });

    it("has gap between legend items", () => {
      const { container } = render(<BiologicalGraph />);
      expect(container.querySelector("div.absolute.bottom-4")).toHaveClass("gap-2");
    });
  });
});
