# TypeScript & Frontend — Best Practices

## Architecture

### Component-Driven Development
- Each component owns its state, behavior, and presentation.
- Keep components small and focused (single responsibility).
- Extract logic into custom hooks for reusability.

### State Management Hierarchy
```
┌─────────────────────────────────────┐
│        Global State (Zustand)       │
│  - Session list, user settings      │
│  - Theme, notifications             │
├─────────────────────────────────────┤
│       Component Local State         │
│  - Form fields, UI toggles          │
│  - Input values, validation         │
├─────────────────────────────────────┤
│       Derived/Computed State        │
│  - Filtered lists, sorted data      │
│  - Memoized calculations            │
└─────────────────────────────────────┘
```

### API Client Pattern
```typescript
// lib/api-client.ts
const api = {
  async get<T>(url: string, options?: RequestInit): Promise<T> {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) throw new APIError(res.status, await res.text());
    return res.json();
  },
  async post<T>(url: string, body: unknown): Promise<T> {
    return api.get<T>(url, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
};
```

---

## Type Safety

### Strict `tsconfig.json`
```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "exactOptionalPropertyTypes": true
  }
}
```

### Discriminated Unions for State Machines
```typescript
type SessionStatus =
  | { kind: "idle" }
  | { kind: "loading"; progress: number }
  | { kind: "running"; sessionId: string }
  | { kind: "error"; message: string }
  | { kind: "completed"; result: SessionResult };

function handleStatus(status: SessionStatus): void {
  switch (status.kind) {
    case "idle": /* ... */ break;
    case "loading":
      console.log(`Progress: ${status.progress}%`);
      break;
    // TypeScript knows these are exhaustive
  }
}
```

### Utility Types
```typescript
// Make all properties optional
type PartialSession = Partial<Session>;

// Remove readonly properties
type Mutable<T> = { -readonly [P in keyof T]: T[P] };

// Extract return type
type SessionResultType = ReturnType<typeof createSession>;

// NonNullable — strip null/undefined
type SafeString = NonNullable<string | null>;
```

---

## React Best Practices

### Functional Components with Hooks
```typescript
// CORRECT
function SessionList({ sessions }: Props) {
  const [filter, setFilter] = useState<string>("");
  const filtered = useMemo(
    () => sessions.filter(s => s.name.includes(filter)),
    [sessions, filter]
  );

  return (
    <ul>
      {filtered.map(session => (
        <SessionItem key={session.id} session={session} />
      ))}
    </ul>
  );
}
```

### Avoid Inline Object/Array Creation in JSX
```typescript
// WRONG — creates new objects on every render, breaks memoization
<Component config={{ key: value }} />

// CORRECT — stable references
const config = useMemo(() => ({ key: value }), [value]);
<Component config={config} />
```

### Error Boundaries
```typescript
class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || <div>Error: {this.state.error?.message}</div>;
    }
    return this.props.children;
  }
}
```

### Custom Hooks for Side Effects
```typescript
function useWebSocket(url: string) {
  const [messages, setMessages] = useState<WSMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(url);
    ws.onopen = () => setIsConnected(true);
    ws.onmessage = (e) => setMessages(prev => [...prev, JSON.parse(e.data)]);
    ws.onclose = () => setIsConnected(false);

    return () => ws.close();
  }, [url]);

  return { messages, isConnected, send };
}
```

---

## Performance

### Code Splitting
```typescript
// Dynamic import for lazy loading
const HeavyChart = lazy(() => import("./components/HeavyChart"));

<Suspense fallback={<Spinner />}>
  <HeavyChart data={chartData} />
</Suspense>
```

### Virtualization for Large Lists
```typescript
import { FixedSizeList } from "react-window";

<FixedSizeList
  height={400}
  itemCount={sessions.length}
  itemSize={60}
>
  {({ index, style }) => (
    <div style={style}>
      <SessionItem session={sessions[index]} />
    </div>
  )}
</FixedSizeList>
```

### Debounce User Input
```typescript
function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
```

---

## Testing

### Component Testing (Vitest + Testing Library)
```typescript
test("renders session list", () => {
  const sessions = [{ id: "1", name: "Test" }];
  render(<SessionList sessions={sessions} />);
  expect(screen.getByText("Test")).toBeInTheDocument();
});

test("handles API error", async () => {
  fetchMock.mockReject(new Error("Network error"));
  render(<SessionList sessions={[]} />);
  expect(screen.getByText(/error/i)).toBeInTheDocument();
});
```

### Integration Testing
```typescript
test("session creation flow", async () => {
  // Mock API
  // Click "New Session"
  // Verify session appears in list
  // Verify composer is active
});
```

### E2E Testing (Playwright)
```typescript
test("complete session lifecycle", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "New Session" }).click();
  await page.getByRole("textbox").fill("Write a function");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Processing...")).toBeVisible();
  // ... verify completion
});
```

---

## Accessibility

### Semantic HTML
```typescript
// Use semantic elements
<nav aria-label="Primary">...</nav>
<main role="main">...</main>
<aside aria-label="Sessions">...</aside>
```

### Keyboard Navigation
```typescript
function useKeyboardNavigation(onSelect: (index: number) => void) {
  return useCallback((e: KeyboardEvent) => {
    if (e.key === "ArrowDown") onSelect(currentIndex + 1);
    if (e.key === "ArrowUp") onSelect(currentIndex - 1);
    if (e.key === "Enter") onActivate();
  }, [onSelect, onActivate]);
}
```

### Focus Management
```typescript
const ref = useRef<HTMLDivElement>(null);
useEffect(() => {
  ref.current?.focus();
}, [isOpen]);
```

---

*Last updated: 2026-08-14*
