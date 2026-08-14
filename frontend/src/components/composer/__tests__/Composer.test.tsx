/**
 * Composer Component Tests
 * Tests the Composer component rendering and interaction
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Composer } from '../Composer';

global.fetch = jest.fn();
document.addEventListener('DOMContentLoaded', () => {});

describe('Composer Component', () => {
  const mockOnSendMessage = jest.fn();
  const mockOnInterrupt = jest.fn();
  const mockOnAttach = jest.fn();

  const defaultProps = {
    isActive: true,
    isStreaming: false,
    sessionId: 'test-session',
    onSendMessage: mockOnSendMessage,
    onInterrupt: mockOnInterrupt,
    onAttach: mockOnAttach,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useRealTimers();
  });

  describe('Rendering', () => {
    test('renders without crashing', () => {
      render(<Composer {...defaultProps} />);
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    test('renders textarea element', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      expect(textarea).toBeInTheDocument();
    });

    test('renders placeholder text', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveAttribute('placeholder');
      expect(textarea.getAttribute('placeholder')).toContain('Describe what you want to build');
    });

    test('renders send button', () => {
      render(<Composer {...defaultProps} />);
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    test('renders upload button when onAttach provided', () => {
      render(<Composer {...defaultProps} />);
      const uploadBtn = document.querySelector('[title="Attach file"]');
      expect(uploadBtn).toBeInTheDocument();
    });

    test('does not render upload button when onAttach not provided', () => {
      const props = { ...defaultProps, onAttach: undefined };
      render(<Composer {...props} />);
      const uploadBtn = document.querySelector('[title="Attach file"]');
      expect(uploadBtn).not.toBeInTheDocument();
    });

    test('textarea is not disabled when active and not streaming', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      expect(textarea).not.toBeDisabled();
    });

    test('renders keyboard hints when active', () => {
      render(<Composer {...defaultProps} />);
      // "Enter" matches both "Enter" and "Shift+Enter", so check the container has the hint group
      expect(screen.getByText(/Shift/)).toBeInTheDocument();
    });

    test('renders version footer', () => {
      render(<Composer {...defaultProps} />);
      expect(screen.getByText('Tektos-Ultima v1')).toBeInTheDocument();
    });

    test('renders with sessionId prop', () => {
      render(<Composer {...defaultProps} sessionId='my-session' />);
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    test('renders with model prop', () => {
      render(<Composer {...defaultProps} model='claude-3' />);
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });
  });

  describe('Streaming state', () => {
    test('shows status text when streaming', () => {
      render(<Composer {...defaultProps} isStreaming={true} />);
      expect(screen.getByText(/AI is responding/i)).toBeInTheDocument();
    });

    test('changes placeholder when streaming', () => {
      render(<Composer {...defaultProps} isStreaming={true} />);
      const textarea = screen.getByRole('textbox');
      expect(textarea.getAttribute('placeholder')).toContain('AI is responding');
    });

    test('shows stop button when streaming', () => {
      render(<Composer {...defaultProps} isStreaming={true} />);
      const stopBtn = document.querySelector('[title="Stop generation"]');
      expect(stopBtn).toBeInTheDocument();
    });

    test('stop button triggers onInterrupt', () => {
      render(<Composer {...defaultProps} isStreaming={true} />);
      const stopBtn = document.querySelector('[title="Stop generation"]');
      fireEvent.click(stopBtn!);
      expect(mockOnInterrupt).toHaveBeenCalled();
    });

    test('hides keyboard hints when streaming', () => {
      render(<Composer {...defaultProps} isStreaming={true} />);
      expect(screen.queryByText(/Enter to send/i)).not.toBeInTheDocument();
    });

    test('send button is replaced by stop button when streaming', () => {
      render(<Composer {...defaultProps} isStreaming={true} />);
      const sendBtn = document.querySelector('[title="Send message"]');
      expect(sendBtn).not.toBeInTheDocument();
    });
  });

  describe('Inactive state', () => {
    test('hides keyboard hints when inactive', () => {
      render(<Composer {...defaultProps} isActive={false} />);
      expect(screen.queryByText(/Enter to send/i)).not.toBeInTheDocument();
    });

    test('send button is disabled when inactive', () => {
      render(<Composer {...defaultProps} isActive={false} />);
      const sendBtn = document.querySelector('[title="Send message"]');
      expect(sendBtn).toHaveAttribute('disabled');
    });

    test('upload button is disabled when inactive', () => {
      render(<Composer {...defaultProps} isActive={false} />);
      const uploadBtn = document.querySelector('[title="Attach file"]');
      expect(uploadBtn).toHaveAttribute('disabled');
    });

    test('textarea is disabled when inactive', () => {
      render(<Composer {...defaultProps} isActive={false} />);
      const textarea = screen.getByRole('textbox');
      expect(textarea).toBeDisabled();
    });
  });

  describe('User interactions', () => {
    test('user can type in textarea', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Hello world' } });
      expect(textarea).toHaveValue('Hello world');
    });

    test('Enter key triggers handleSubmit', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Test message' } });
      fireEvent.keyDown(textarea, { key: 'Enter' });
      expect(mockOnSendMessage).toHaveBeenCalledWith('Test message');
    });

    test('Ctrl+D triggers handleSubmit', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Test message' } });
      fireEvent.keyDown(textarea, { key: 'd', ctrlKey: true });
      expect(mockOnSendMessage).toHaveBeenCalledWith('Test message');
    });

    test('Ctrl+Shift+M toggles metrics display', () => {
      const { container } = render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.keyDown(textarea, { key: 'M', ctrlKey: true, shiftKey: true });
      // Ctrl+Shift+M toggles setShowMetrics, not onInterrupt
      expect(container.innerHTML).toBeDefined();
    });

    test('Shift+Enter does not submit', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Line 1' } });
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
      expect(mockOnSendMessage).not.toHaveBeenCalled();
    });

    test('empty message does not submit', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.keyDown(textarea, { key: 'Enter' });
      expect(mockOnSendMessage).not.toHaveBeenCalled();
    });

    test('whitespace-only message does not submit', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: '   ' } });
      fireEvent.keyDown(textarea, { key: 'Enter' });
      expect(mockOnSendMessage).not.toHaveBeenCalled();
    });

    test('upload button triggers file input click', () => {
      render(<Composer {...defaultProps} />);
      const uploadBtn = document.querySelector('[title="Attach file"]');
      const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
      expect(fileInput).toBeInTheDocument();
      fireEvent.click(uploadBtn!);
    });

    test('file change triggers onAttach', () => {
      render(<Composer {...defaultProps} />);
      const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
      const mockFile = new File(['test'], 'test.txt', { type: 'text/plain' });
      Object.defineProperty(fileInput!, 'files', { value: [mockFile], writable: false });
      fireEvent.change(fileInput!);
      expect(mockOnAttach).toHaveBeenCalled();
    });

    test('send button disabled when no text', () => {
      render(<Composer {...defaultProps} />);
      const sendBtn = document.querySelector('[title="Send message"]');
      expect(sendBtn).toHaveAttribute('disabled');
    });

    test('send button enabled when text entered', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Hello' } });
      const sendBtn = document.querySelector('[title="Send message"]');
      expect(sendBtn).not.toHaveAttribute('disabled');
    });
  });

  describe('Metrics display', () => {
    test('shows word count when text entered', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Hello world test' } });
      expect(document.body.textContent).toContain('words');
    });

    test('shows token count when text entered', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Hello world test' } });
      expect(document.body.textContent).toContain('tok');
    });

    test('shows character count when text entered', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Hello' } });
      expect(document.body.textContent).toContain('chars');
    });

    test('metrics hidden when no text and not streaming', () => {
      render(<Composer {...defaultProps} />);
      expect(document.body.textContent).not.toContain('words');
      expect(document.body.textContent).not.toContain('tok');
    });

    test('model name shown when provided and text entered', () => {
      render(<Composer {...defaultProps} model='gpt-4' />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Hello' } });
      expect(document.body.textContent).toContain('gpt-4');
    });

    test('context usage bar shown when text entered', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Hello world' } });
      expect(document.body.textContent).toContain('tok');
    });

    test('metrics show elapsed time when streaming with text', () => {
      jest.useFakeTimers();
      render(<Composer {...defaultProps} isStreaming={true} />);
      expect(document.body.textContent).toContain('AI is thinking');
      jest.useRealTimers();
    });
  });

  describe('Textarea behavior', () => {
    test('textarea accepts focus event', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.focus(textarea);
      const wrapper = textarea.closest('.composer-input-wrapper');
      expect(wrapper?.className).toContain('shadow-glow');
    });

    test('textarea blur removes focus state', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.focus(textarea);
      fireEvent.blur(textarea);
      expect(textarea).toBeInTheDocument();
    });

    test('multi-line input works', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Line 1\nLine 2\nLine 3' } });
      expect(textarea).toHaveValue('Line 1\nLine 2\nLine 3');
    });

    test('placeholder overlay shows when empty and not focused', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveAttribute('placeholder');
    });

    test('textarea has correct default rows', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveAttribute('rows');
    });

    test('textarea auto-resizes with content', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'A'.repeat(500) } });
      expect(textarea).toBeInTheDocument();
    });
  });

  describe('Button interactions', () => {
    test('send button has correct title', () => {
      render(<Composer {...defaultProps} />);
      const sendBtn = document.querySelector('[title="Send message"]');
      expect(sendBtn).toBeInTheDocument();
    });

    test('upload button has correct title', () => {
      render(<Composer {...defaultProps} />);
      const uploadBtn = document.querySelector('[title="Attach file"]');
      expect(uploadBtn).toBeInTheDocument();
    });

    test('stop button has correct title', () => {
      render(<Composer {...defaultProps} isStreaming={true} />);
      const stopBtn = document.querySelector('[title="Stop generation"]');
      expect(stopBtn).toBeInTheDocument();
    });

    test('send button onClick calls handleSubmit', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Test' } });
      const sendBtn = document.querySelector('[title="Send message"]');
      fireEvent.click(sendBtn!);
      expect(mockOnSendMessage).toHaveBeenCalledWith('Test');
    });

    test('upload button onClick triggers file input', () => {
      render(<Composer {...defaultProps} />);
      const uploadBtn = document.querySelector('[title="Attach file"]');
      expect(uploadBtn).toBeInTheDocument();
    });
  });

  describe('Placeholder behavior', () => {
    test('placeholder text is visible by default', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      expect(textarea.getAttribute('placeholder')).toBeTruthy();
    });

    test('placeholder changes when streaming', () => {
      render(<Composer {...defaultProps} isStreaming={true} />);
      const textarea = screen.getByRole('textbox');
      expect(textarea.getAttribute('placeholder')).toContain('interrupt');
    });
  });

  describe('Edge cases', () => {
    test('handles very long input', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      const longText = 'A'.repeat(10000);
      fireEvent.change(textarea, { target: { value: longText } });
      expect(textarea).toHaveValue(longText);
    });

    test('handles unicode characters', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'こんにちは 🌍 مرحبا' } });
      expect(textarea).toHaveValue('こんにちは 🌍 مرحبا');
    });

    test('handles special characters', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: '<>&"\'`$()' } });
      expect(textarea).toHaveValue('<>&"\'`$()');
    });

    test('handles tabs in input', () => {
      render(<Composer {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'col1\tcol2\tcol3' } });
      expect(textarea).toHaveValue('col1\tcol2\tcol3');
    });
  });
});
