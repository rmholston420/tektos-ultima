import '@testing-library/jest-dom';

// Mock Next.js dynamic import
jest.mock('next/dynamic', () => (component: any) => {
  const mockComponent = jest.fn((props: any) => component(props));
  (mockComponent as any).ssr = false;
  return mockComponent;
});

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock IntersectionObserver
global.IntersectionObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock ResizeObserver
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock scrollIntoView
Element.prototype.scrollIntoView = jest.fn();

// Mock HTMLCanvasElement.prototype.getContext
HTMLCanvasElement.prototype.getContext = jest.fn(() => ({
  beginPath: jest.fn(),
  arc: jest.fn(),
  fillStyle: '',
  fill: jest.fn(),
  clearRect: jest.fn(),
  save: jest.fn(),
  restore: jest.fn(),
  translate: jest.fn(),
  rotate: jest.fn(),
  scale: jest.fn(),
  stroke: jest.fn(),
  rect: jest.fn(),
  fillText: jest.fn(),
  measureText: jest.fn(() => ({ width: 0 })),
  createLinearGradient: jest.fn(),
  createRadialGradient: jest.fn(),
  getImageData: jest.fn(),
  putImageData: jest.fn(),
  drawImage: jest.fn(),
  setTransform: jest.fn(),
  createPattern: jest.fn(),
  createImageData: jest.fn(),
  lineTo: jest.fn(),
  moveTo: jest.fn(),
  closePath: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
})) as any;
