/**
 * Tests for AxiomsPanel — loading, filtering, verification, progress.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

jest.mock("@/lib/api", () => ({
  api: {
    getAxioms: jest.fn(),
    verifyAxiom: jest.fn(),
  },
  Axiom: Object,
}));

import { AxiomsPanel } from "../AxiomsPanel";
import * as api from "@/lib/api";

const mockGetAxioms = api.api.getAxioms as jest.Mock;
const mockVerifyAxiom = api.api.verifyAxiom as jest.Mock;

describe("AxiomsPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetAxioms.mockReset();
    mockVerifyAxiom.mockReset();
  });

  function mockAxioms() {
    return [
      {
        id: "AX-001",
        description: "All code must be tested",
        status: "verified",
        category: "quality",
        prerequisites: [],
      },
      {
        id: "AX-002",
        description: "No unhandled exceptions",
        status: "in_progress",
        category: "quality",
        prerequisites: ["AX-001"],
      },
      {
        id: "AX-003",
        description: "All APIs must be documented",
        status: "blocked",
        category: "documentation",
        prerequisites: ["AX-001"],
      },
    ];
  }

  it("renders header", async () => {
    mockGetAxioms.mockResolvedValue([]);
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("Axiom System")).toBeInTheDocument());
  });

  it("renders loading state", async () => {
    mockGetAxioms.mockImplementation(() => new Promise(() => {}));
    render(<AxiomsPanel />);
    expect(screen.getByText("Loading axioms...")).toBeInTheDocument();
  });

  it("renders progress percentage", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("33% complete (1/3)")).toBeInTheDocument());
  });

  it("renders progress bar", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("Axiom System")).toBeInTheDocument());
    const progressBar = document.querySelector('[class*="bg-gradient-to-r"]');
    expect(progressBar).toBeInTheDocument();
  });

  it("renders All filter button", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("All")).toBeInTheDocument());
  });

  it("renders category filter buttons", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("quality")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("documentation")).toBeInTheDocument());
  });

  it("renders axiom cards with IDs", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    // Use descriptions (unique) to verify axiom cards render
    await waitFor(() => expect(screen.getByText("All code must be tested")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("No unhandled exceptions")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("All APIs must be documented")).toBeInTheDocument());
  });

  it("renders axiom descriptions", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("All code must be tested")).toBeInTheDocument());
  });

  it("renders status badges", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("verified")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("in_progress")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("blocked")).toBeInTheDocument());
  });

  it("renders status icons", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("Axiom System")).toBeInTheDocument());
    // Icons are rendered as text content in spans
    const iconTexts = screen.queryAllByText(/⏳|✅|🚫/);
    expect(iconTexts.length).toBeGreaterThanOrEqual(1);
  });

  it("renders prerequisites", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getAllByText("Requires:")).toHaveLength(2));
  });

  it("does not render prerequisites for axioms with none", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("All code must be tested")).toBeInTheDocument());
    // AX-001 has no prerequisites, so "Requires:" should appear only for AX-002 and AX-003
    const requiresEls = screen.queryAllByText("Requires:");
    expect(requiresEls.length).toBe(2);
  });

  it("shows Verify button for non-verified axioms", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("No unhandled exceptions")).toBeInTheDocument());
    const verifyButtons = screen.getAllByText("Verify");
    expect(verifyButtons).toHaveLength(2);
  });

  it("does not show Verify button for verified axioms", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("All code must be tested")).toBeInTheDocument());
    const verifyButtons = screen.getAllByText("Verify");
    expect(verifyButtons).toHaveLength(2); // Only AX-002 and AX-003
  });

  it("filters by category", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("All code must be tested")).toBeInTheDocument());
    fireEvent.click(screen.getByText("quality"));
    await waitFor(() => expect(screen.getByText("All code must be tested")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("No unhandled exceptions")).toBeInTheDocument());
    expect(screen.queryByText("All APIs must be documented")).not.toBeInTheDocument();
  });

  it("filters back to all", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("All code must be tested")).toBeInTheDocument());
    fireEvent.click(screen.getByText("quality"));
    fireEvent.click(screen.getByText("All"));
    await waitFor(() => expect(screen.getByText("All code must be tested")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("All APIs must be documented")).toBeInTheDocument());
  });

  it("verifies an axiom", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("No unhandled exceptions")).toBeInTheDocument());
    const verifyButtons = screen.getAllByText("Verify");
    fireEvent.click(verifyButtons[0]);
    await waitFor(() => expect(mockVerifyAxiom).toHaveBeenCalledWith("AX-002"));
  });

  it("updates progress after verification", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("33% complete (1/3)")).toBeInTheDocument());
    const verifyButtons = screen.getAllByText("Verify");
    fireEvent.click(verifyButtons[0]);
    await waitFor(() => expect(mockVerifyAxiom).toHaveBeenCalledWith("AX-002"));
    await waitFor(() => expect(screen.getByText("67% complete (2/3)")).toBeInTheDocument());
  });

  it("handles verify error gracefully", async () => {
    mockGetAxioms.mockResolvedValue(mockAxioms());
    mockVerifyAxiom.mockRejectedValue(new Error("Network error"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("No unhandled exceptions")).toBeInTheDocument());
    const verifyButtons = screen.getAllByText("Verify");
    fireEvent.click(verifyButtons[0]);
    await waitFor(() => expect(consoleSpy).toHaveBeenCalledWith("Failed to verify axiom:", expect.any(Error)));
    consoleSpy.mockRestore();
  });

  it("renders 0% when no axioms", async () => {
    mockGetAxioms.mockResolvedValue([]);
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("0% complete (0/0)")).toBeInTheDocument());
  });

  it("renders 100% when all verified", async () => {
    mockGetAxioms.mockResolvedValue([
      { id: "AX-001", description: "Test", status: "verified", category: "test", prerequisites: [] },
    ]);
    render(<AxiomsPanel />);
    await waitFor(() => expect(screen.getByText("100% complete (1/1)")).toBeInTheDocument());
  });
});
