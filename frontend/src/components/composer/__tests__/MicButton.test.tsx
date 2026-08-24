/**
 * Tests for MicButton component.
 */

import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MicButton } from "../MicButton";

// Mock navigator.mediaDevices
const mockGetUserMedia = jest.fn();
Object.defineProperty(navigator, "mediaDevices", {
  value: { getUserMedia: mockGetUserMedia },
  writable: true,
});

// Mock AudioContext
class MockAudioContext {
  createMediaStreamSource() {
    return { connect: jest.fn() };
  }
  createAnalyser() {
    return {
      fftSize: 0,
      getByteFrequencyData: jest.fn(),
    };
  }
}
(global as any).AudioContext = MockAudioContext;

// Mock MediaRecorder
class MockMediaRecorder {
  state = "inactive";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  chunks: Blob[] = [];

  start() {
    this.state = "recording";
  }

  stop() {
    this.state = "inactive";
    if (this.onstop) this.onstop();
  }
}
(global as any).MediaRecorder = MockMediaRecorder;

// Mock fetch
(global as any).fetch = jest.fn();

describe("MicButton", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetUserMedia.mockResolvedValue({
      getTracks: () => [],
    });
  });

  it("renders the button", () => {
    render(<MicButton />);
    const button = screen.getByRole("button", { name: /record voice/i });
    expect(button).toBeInTheDocument();
  });

  it("calls onTranscript when transcription succeeds", async () => {
    const onTranscript = jest.fn();
    (global as any).fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ text: "hello world" }),
    });

    render(<MicButton onTranscript={onTranscript} />);
    const button = screen.getByRole("button", { name: /record voice/i });

    // Start recording
    await act(async () => {
      fireEvent.click(button);
    });

    // Wait for recording to start
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /stop recording/i })).toBeInTheDocument();
    });

    // Stop recording
    await act(async () => {
      const stopButton = screen.getByRole("button", { name: /stop recording/i });
      fireEvent.click(stopButton);
    });

    // Wait for transcription
    await waitFor(() => {
      expect(onTranscript).toHaveBeenCalledWith("hello world");
    });
  });

  it("shows error when microphone access is denied", async () => {
    mockGetUserMedia.mockRejectedValue(new Error("Permission denied"));

    render(<MicButton />);
    const button = screen.getByRole("button", { name: /record voice/i });
    await act(async () => {
      fireEvent.click(button);
    });

    await waitFor(() => {
      expect(screen.getByText(/microphone access denied/i)).toBeInTheDocument();
    });
  });

  it("shows transcribing state", async () => {
    (global as any).fetch.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(() => resolve({ ok: true, json: async () => ({ text: "test" }) }), 100)
        )
    );

    render(<MicButton />);
    const button = screen.getByRole("button", { name: /record voice/i });
    await act(async () => {
      fireEvent.click(button);
    });

    // Wait for recording to start
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /stop recording/i })).toBeInTheDocument();
    });

    // Stop recording
    await act(async () => {
      const stopButton = screen.getByRole("button", { name: /stop recording/i });
      fireEvent.click(stopButton);
    });

    // Should show transcribing state
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /transcribing/i })).toBeInTheDocument();
    });
  });
});
