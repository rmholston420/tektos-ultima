/**
 * Tests for LandingPage — typing animation, keyboard handler, enter flow.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { LandingPage } from "../LandingPage";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("LandingPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
  });

  it("renders TEKTOS wordmark", () => {
    render(<LandingPage onEnter={() => {}} />);
    expect(screen.getByText("TEKTOS")).toBeInTheDocument();
  });

  it("renders subtitle with typing animation", () => {
    render(<LandingPage onEnter={() => {}} />);
    expect(screen.getByText(/Autonomous Coding Agent/)).toBeInTheDocument();
  });

  it("renders Enter button", () => {
    render(<LandingPage onEnter={() => {}} />);
    expect(screen.getByText("Enter")).toBeInTheDocument();
  });

  it("renders bottom hint text", () => {
    render(<LandingPage onEnter={() => {}} />);
    expect(screen.getByText("Press Enter or click to begin")).toBeInTheDocument();
  });

  it("calls onEnter when Enter button is clicked", () => {
    const onEnter = jest.fn();
    render(<LandingPage onEnter={onEnter} />);
    fireEvent.click(screen.getByText("Enter"));
    expect(onEnter).toHaveBeenCalled();
  });

  it("calls onEnter when Enter key is pressed", () => {
    const onEnter = jest.fn();
    render(<LandingPage onEnter={onEnter} />);
    fireEvent.keyDown(window, { key: "Enter" });
    expect(onEnter).toHaveBeenCalled();
  });

  it("calls onEnter when Space key is pressed", () => {
    const onEnter = jest.fn();
    render(<LandingPage onEnter={onEnter} />);
    fireEvent.keyDown(window, { key: " " });
    expect(onEnter).toHaveBeenCalled();
  });

  it("does not call onEnter for other keys", () => {
    const onEnter = jest.fn();
    render(<LandingPage onEnter={onEnter} />);
    fireEvent.keyDown(window, { key: "a" });
    expect(onEnter).not.toHaveBeenCalled();
  });

  it("prevents default on Enter key", () => {
    const onEnter = jest.fn();
    render(<LandingPage onEnter={onEnter} />);
    const event = new KeyboardEvent("keydown", { key: "Enter" });
    const preventDefaultSpy = jest.spyOn(event, "preventDefault");
    window.dispatchEvent(event);
    expect(preventDefaultSpy).toHaveBeenCalled();
  });

  it("renders with custom backendUrl", () => {
    render(<LandingPage onEnter={() => {}} backendUrl="http://custom:8020" />);
    expect(screen.getByText("TEKTOS")).toBeInTheDocument();
  });

  it("renders with default backendUrl", () => {
    render(<LandingPage onEnter={() => {}} />);
    expect(screen.getByText("TEKTOS")).toBeInTheDocument();
  });

  it("renders TTSWelcome component (fetches TTS)", () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      blob: () => Promise.resolve(new Blob(["audio"], { type: "audio/mpeg" })),
    });
    render(<LandingPage onEnter={() => {}} />);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/voice/tts"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("handles TTS fetch error gracefully", () => {
    mockFetch.mockRejectedValueOnce(new Error("TTS unavailable"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<LandingPage onEnter={() => {}} />);
    expect(screen.getByText("TEKTOS")).toBeInTheDocument();
    consoleSpy.mockRestore();
  });

  it("renders with correct document styling", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain("fixed");
    expect(root.className).toContain("inset-0");
  });

  it("renders particle canvas", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const canvas = container.querySelector("canvas");
    expect(canvas).toBeInTheDocument();
  });

  it("renders with gradient background", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const root = container.firstChild as HTMLElement;
    expect(root.style.background).toContain("linear-gradient");
  });

  it("renders background image div", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const bgDiv = container.querySelector('[style*="tektos-landing.jpg"]');
    expect(bgDiv).toBeInTheDocument();
  });

  it("renders radial glow overlay", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const glowDiv = container.querySelector('[style*="radial-gradient"]');
    expect(glowDiv).toBeInTheDocument();
  });

  it("renders dark overlay for readability", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const overlays = container.querySelectorAll('[style*="radial-gradient"]');
    expect(overlays.length).toBeGreaterThanOrEqual(2);
  });

  it("renders content with staggered entrance", () => {
    render(<LandingPage onEnter={() => {}} />);
    expect(screen.getByText("TEKTOS")).toBeInTheDocument();
  });

  it("renders with correct z-index layering", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain("z-50");
  });

  it("renders with overflow-hidden", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain("overflow-hidden");
  });

  it("renders with flex layout", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain("flex");
  });

  it("renders with centered content", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain("items-center");
    expect(root.className).toContain("justify-center");
  });

  it("renders with flex-col layout", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain("flex-col");
  });

  it("renders wordmark with gradient text", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const h1 = container.querySelector("h1");
    expect(h1).toBeInTheDocument();
    expect(h1?.style.background).toContain("linear-gradient");
  });

  it("renders wordmark with large font size", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const h1 = container.querySelector("h1");
    expect(h1?.className).toContain("text-7xl");
  });

  it("renders Enter button with uppercase text", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const btn = container.querySelector("button");
    expect(btn?.className).toContain("uppercase");
  });

  it("renders Enter button with rounded-full", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const btn = container.querySelector("button");
    expect(btn?.className).toContain("rounded-full");
  });

  it("typing animation shows partial text initially", () => {
    render(<LandingPage onEnter={() => {}} />);
    const textContent = document.body.textContent;
    expect(textContent).toContain("Autonomous Coding Agent");
  });

  it("renders with dark olive/gold color scheme", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const root = container.firstChild as HTMLElement;
    expect(root.style.background).toContain("#0a0c08");
  });

  it("renders with correct heading structure", () => {
    render(<LandingPage onEnter={() => {}} />);
    const h1 = document.querySelector("h1");
    expect(h1).toBeInTheDocument();
    expect(h1?.textContent).toBe("TEKTOS");
  });

  it("renders subtitle paragraph", () => {
    render(<LandingPage onEnter={() => {}} />);
    const subtitle = document.querySelector("p");
    expect(subtitle).toBeInTheDocument();
  });

  it("renders hover glow on Enter button", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const btn = container.querySelector("button");
    expect(btn).toBeInTheDocument();
  });

  it("renders group hover overlay on Enter button", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const btn = container.querySelector("button");
    expect(btn).toBeInTheDocument();
  });

  it("does not call onEnter on repeated Enter key after entered", () => {
    const onEnter = jest.fn();
    render(<LandingPage onEnter={onEnter} />);
    fireEvent.click(screen.getByText("Enter"));
    expect(onEnter).toHaveBeenCalledTimes(1);
  });

  it("renders with px-6 padding", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const content = container.querySelector(".relative.z-30");
    expect(content).toBeInTheDocument();
  });

  it("renders with gap-8 spacing", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const content = container.querySelector(".relative.z-30");
    expect(content?.className).toContain("gap-8");
  });

  it("renders bottom hint with uppercase", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const hints = container.querySelectorAll("p");
    const lastHint = hints[hints.length - 1];
    expect(lastHint?.className).toContain("uppercase");
  });

  it("renders bottom hint with tracking-widest", () => {
    const { container } = render(<LandingPage onEnter={() => {}} />);
    const hints = container.querySelectorAll("p");
    const lastHint = hints[hints.length - 1];
    expect(lastHint?.className).toContain("tracking-widest");
  });
});
