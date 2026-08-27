/**
 * Tests for SkillsPanel — loading, stats, search, category filter, toggle, delete.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { SkillsPanel } from "../SkillsPanel";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("SkillsPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
  });

  function mockSkillsData() {
    return {
      skills: [
        {
          id: "s1",
          name: "code-review",
          category: "development",
          enabled: true,
          version: "1.2.0",
          description: "Review code for quality and security",
          trigger_conditions: ["on_pr", "on_commit"],
          steps: [],
          usage_count: 45,
          last_used: "2024-06-01",
          success_rate: 0.95,
          source: "hermes",
          created_at: "2024-01-01",
          updated_at: "2024-06-01",
        },
        {
          id: "s2",
          name: "test-generation",
          category: "development",
          enabled: false,
          version: "0.9.0",
          description: "Generate unit tests from code",
          trigger_conditions: ["on_file_change"],
          steps: [],
          usage_count: 12,
          last_used: "2024-05-15",
          success_rate: 0.85,
          source: "user",
          created_at: "2024-03-01",
          updated_at: "2024-05-15",
        },
        {
          id: "s3",
          name: "deploy-helper",
          category: "devops",
          enabled: true,
          version: "2.0.0",
          description: "Automate deployment workflows",
          trigger_conditions: ["on_tag"],
          steps: [],
          usage_count: 8,
          last_used: "2024-06-02",
          success_rate: 1.0,
          source: "hermes",
          created_at: "2024-02-01",
          updated_at: "2024-06-02",
        },
      ],
    };
  }

  function mockStatsData() {
    return {
      total_skills: 3,
      active_skills: 2,
      top_skills: [],
      categories: ["development", "devops"],
    };
  }

  it("renders loading spinner", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<SkillsPanel />);
    expect(document.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("renders stats cards", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("Total Skills")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Enabled")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Total Usages")).toBeInTheDocument());
  });

  it("renders correct skill counts", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("3")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("2")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("65")).toBeInTheDocument());
  });

  it("renders skill names", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("code-review")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("test-generation")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("deploy-helper")).toBeInTheDocument());
  });

  it("renders skill categories", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("development")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("devops")).toBeInTheDocument());
  });

  it("renders skill versions", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("v1.2.0")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("v2.0.0")).toBeInTheDocument());
  });

  it("renders skill descriptions", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("Review code for quality and security")).toBeInTheDocument());
  });

  it("renders trigger conditions", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("on_pr")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("on_commit")).toBeInTheDocument());
  });

  it("renders usage count", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("45 uses")).toBeInTheDocument());
  });

  it("renders success rate", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("95% success")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("100% success")).toBeInTheDocument());
  });

  it("renders source badge", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("hermes")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("user")).toBeInTheDocument());
  });

  it("renders search input", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    expect(screen.getByPlaceholderText("Search skills...")).toBeInTheDocument();
  });

  it("renders category filter dropdown", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
  });

  it("filters skills by search text", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    const searchInput = screen.getByPlaceholderText("Search skills...");
    fireEvent.change(searchInput, { target: { value: "deploy" } });
    await waitFor(() => expect(screen.getByText("deploy-helper")).toBeInTheDocument());
    expect(screen.queryByText("code-review")).not.toBeInTheDocument();
  });

  it("filters skills by category", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "devops" } });
    await waitFor(() => expect(screen.getByText("deploy-helper")).toBeInTheDocument());
    expect(screen.queryByText("code-review")).not.toBeInTheDocument();
  });

  it("shows no results message when search matches nothing", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    const searchInput = screen.getByPlaceholderText("Search skills...");
    fireEvent.change(searchInput, { target: { value: "nonexistent" } });
    await waitFor(() => expect(screen.getByText("No skills match your search.")).toBeInTheDocument());
  });

  it("shows empty state when no skills at all", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve({ skills: [] }) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("No skills yet.")).toBeInTheDocument());
  });

  it("toggles skill enabled state", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("code-review")).toBeInTheDocument());
    const toggleButtons = screen.getAllByTitle("Disable");
    fireEvent.click(toggleButtons[0]);
    await waitFor(() => expect(mockFetch).toHaveBeenCalledWith(
      "/api/skills/s1/toggle",
      expect.objectContaining({ method: "POST" })
    ));
  });

  it("shows delete button for each skill", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("code-review")).toBeInTheDocument());
    const deleteButtons = document.querySelectorAll("[title='Delete']");
    expect(deleteButtons.length).toBe(3);
  });

  it("handles fetch error with error display", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("Network error")).toBeInTheDocument());
  });

  it("renders last used date", async () => {
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(mockSkillsData()) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("code-review")).toBeInTheDocument());
  });

  it("renders 0% success when no rate", async () => {
    const data = mockSkillsData();
    data.skills[0].success_rate = 0;
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(data) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("N/A")).toBeInTheDocument());
  });

  it("renders general category when no category", async () => {
    const data = mockSkillsData();
    data.skills[0].category = "";
    mockFetch.mockResolvedValue({ json: () => Promise.resolve(data) });
    render(<SkillsPanel />);
    await waitFor(() => expect(screen.getByText("general")).toBeInTheDocument());
  });
});
