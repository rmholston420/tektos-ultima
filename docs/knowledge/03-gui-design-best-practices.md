# GUI Design — Best Practices

## Principles

### Information Hierarchy
- Primary actions should be most prominent (size, color, position).
- Secondary actions are visible but less dominant.
- Tertiary actions are accessible but not intrusive.
- Follow the F-pattern or Z-pattern for reading flow.

### Consistency
- Same action always produces the same result.
- Same visual treatment always means the same thing.
- Error messages follow a consistent format.
- Icons have consistent meaning across the application.

### Feedback
- Every user action gets immediate feedback.
- Loading states are explicit, not implicit.
- Progress is visible and measurable.
- Errors are actionable, not just descriptive.

---

## Layout Patterns

### Three-Panel Layout (Tektos Pattern)
```
┌─────────────────────────────────────────────────────┐
│  HEADER: Branding, Status, Settings                   │
├──────────┬──────────────────────────────────────────┤
│          │  MAIN AREA                                │
│  SIDEBAR │  - Transcript / Code / Content            │
│  -       │  - Interactive elements                   │
│  Session │  - Status indicators                      │
│  List    │                                           │
│          │                                           │
│          │                                           │
├──────────┴──────────────────────────────────────────┤
│  COMPOSER: Input area with action buttons             │
├─────────────────────────────────────────────────────┤
│  FOOTER: Version, System Status                       │
└─────────────────────────────────────────────────────┘
```

### Responsive Breakpoints
```typescript
const breakpoints = {
  mobile: 640,    // Single column, stacked layout
  tablet: 768,    // Two columns, collapsible sidebar
  desktop: 1024,  // Three columns, full sidebar
  wide: 1280,     // Additional breathing room
} as const;
```

---

## Interaction Design

### State Management for UI
```typescript
type ComponentState =
  | { status: "idle" }
  | { status: "loading"; progress: number }
  | { status: "error"; message: string }
  | { status: "success"; data: T };

function Component({ state }: Props) {
  switch (state.status) {
    case "idle": return <EmptyState />;
    case "loading": return <LoadingBar progress={state.progress} />;
    case "error": return <ErrorBanner message={state.message} />;
    case "success": return <DataDisplay data={state.data} />;
  }
}
```

### Progressive Disclosure
- Show only what's needed, when it's needed.
- Expandable sections, tooltips, and modals.
- Don't overwhelm with information density.

### Undo/Redo
```typescript
function useUndoRedo<T>(initial: T) {
  const [history, setHistory] = useState<T[]>([initial]);
  const [index, setIndex] = useState(0);

  const undo = () => index > 0 && setIndex(index - 1);
  const redo = () => index < history.length - 1 && setIndex(index + 1);
  const push = (value: T) => {
    setHistory(prev => [...prev.slice(0, index + 1), value]);
    setIndex(index + 1);
  };

  return { undo, redo, push, current: history[index] };
}
```

---

## Visual Design

### Color System
```typescript
const colors = {
  primary: { 50: "#eef2ff", ..., 900: "#1e1b4b" },
  secondary: { 50: "#f0fdf4", ..., 900: "#14532d" },
  error: { 50: "#fef2f2", ..., 900: "#7f1d1d" },
  warning: { 50: "#fffbeb", ..., 900: "#78350f" },
  neutral: { 50: "#fafafa", ..., 950: "#0a0a0a" },
} as const;
```

### Typography Scale
```typescript
const typography = {
  xs: { fontSize: "0.75rem", lineHeight: "1rem" },
  sm: { fontSize: "0.875rem", lineHeight: "1.25rem" },
  base: { fontSize: "1rem", lineHeight: "1.5rem" },
  lg: { fontSize: "1.125rem", lineHeight: "1.75rem" },
  xl: { fontSize: "1.25rem", lineHeight: "1.75rem" },
  "2xl": { fontSize: "1.5rem", lineHeight: "2rem" },
} as const;
```

### Spacing Scale
```typescript
const spacing = {
  0: "0",
  1: "0.25rem",
  2: "0.5rem",
  3: "0.75rem",
  4: "1rem",
  6: "1.5rem",
  8: "2rem",
  12: "3rem",
  16: "4rem",
} as const;
```

---

## Dark Mode

### Design for Dark First
- High contrast by default.
- Avoid pure black (#000000) — use dark gray (#1a1a1a) to reduce eye strain.
- Ensure all interactive elements are clearly visible.

### Color Adaptation
```typescript
const darkColors = {
  bg: "#1a1a1a",
  surface: "#2d2d2d",
  border: "#404040",
  text: "#e5e5e5",
  textMuted: "#888888",
  primary: "#3b82f6",
  error: "#ef4444",
};
```

---

## Error States

### Error Message Format
```
┌─────────────────────────────────────────────────────┐
│  ⚠️  Title: Clear description of what went wrong      │
│      Context: What the user was doing                  │
│      Suggestion: What they can do to fix it            │
│      [Retry] [Cancel]                                  │
└─────────────────────────────────────────────────────┘
```

### Graceful Degradation
- If API fails, show cached data with "stale" indicator.
- If loading fails, show error with retry option.
- If validation fails, show field-level errors inline.

---

## Keyboard Shortcuts

### Standard Shortcuts
| Action | Shortcut |
|--------|----------|
| New session | Ctrl+N |
| Search | Ctrl+F |
| Send message | Enter |
| New line in composer | Shift+Enter |
| Interrupt | Ctrl+C |
| Settings | Ctrl+, |

### Custom Hooks
```typescript
function useKeyboardShortcut(key: string, callback: () => void) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === key && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        callback();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [key, callback]);
}
```

---

## Accessibility (WCAG 2.1 AA)

### Minimum Requirements
- Color contrast ratio: 4.5:1 for normal text, 3:1 for large text.
- All interactive elements must be keyboard accessible.
- Focus indicators must be visible.
- Alt text for images, ARIA labels for icons.

### Testing
```typescript
// axe-core for automated accessibility testing
import { axe } from "jest-axe";

test("no accessibility violations", async () => {
  const { container } = render(<Component />);
  const results = await axe(container);
  expect(results.violations).toHaveLength(0);
});
```

---

*Last updated: 2026-08-14*
