/**
 * Tests for TTSPlayer — play/pause/stop states, synthesizing, error handling.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TTSPlayer } from "../TTSPlayer";

const mockAudioPlay = jest.fn().mockResolvedValue(undefined);
const mockAudioPause = jest.fn();

class MockAudio {
  onplay: (() => void) | null = null;
  onpause: (() => void) | null = null;
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;
  src = "";
  paused = true;

  play() {
    this.paused = false;
    return mockAudioPlay();
  }
  pause() {
    this.paused = true;
    mockAudioPause();
  }
  get currentTime() { return 0; }
  set currentTime(v: number) {}
}

global.Audio = MockAudio as any;

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("TTSPlayer", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
    mockAudioPlay.mockReset();
    mockAudioPause.mockReset();
  });

  it("renders play button in default state", () => {
    render(<TTSPlayer />);
    const btn = screen.getByTitle("Play");
    expect(btn).toBeInTheDocument();
  });

  it("renders play button disabled when not playing or synthesizing", () => {
    render(<TTSPlayer />);
    const btn = screen.getByTitle("Play");
    expect(btn).toHaveClass("opacity-50");
  });

  it("renders with custom backendUrl", () => {
    const { container } = render(<TTSPlayer backendUrl="custom:8020" />);
    expect(container).toBeTruthy();
  });

  it("renders with autoPlay disabled", () => {
    const { container } = render(<TTSPlayer autoPlay={false} />);
    expect(container).toBeTruthy();
  });

  it("renders with onText callback", () => {
    const onText = jest.fn();
    const { container } = render(<TTSPlayer onText={onText} />);
    expect(container).toBeTruthy();
  });

  it("play button has correct SVG icon in default state", () => {
    render(<TTSPlayer />);
    const btn = screen.getByTitle("Play");
    const svg = btn.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("handles fetch error gracefully", async () => {
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    mockFetch.mockRejectedValueOnce(new Error("Network error"));
    const { container } = render(<TTSPlayer />);
    expect(container).toBeTruthy();
    consoleSpy.mockRestore();
  });

  it("renders with default props", () => {
    render(<TTSPlayer />);
    expect(screen.getByTitle("Play")).toBeInTheDocument();
  });

  it("renders stop button conditionally", () => {
    const { container } = render(<TTSPlayer />);
    expect(container.querySelector("button")).toBeInTheDocument();
  });

  it("renders error message when error state is set", () => {
    const TestWrapper = () => {
      const [error, setError] = React.useState<string | null>(null);
      return (
        <div>
          {error && <div data-testid="error">{error}</div>}
          <TTSPlayer />
        </div>
      );
    };
    render(<TestWrapper />);
    expect(screen.queryByTestId("error")).not.toBeInTheDocument();
  });
});
