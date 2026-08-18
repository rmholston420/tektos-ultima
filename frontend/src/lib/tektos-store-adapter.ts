/**
 * Tektos-Ultima v1 — ExternalStoreAdapter for @assistant-ui/react
 * 
 * Bridges WebSocket events to @assistant-ui/react streaming runtime.
 * Implements the ExternalStoreAdapter interface so the library handles:
 * - Message accumulation with proper identity
 * - Streaming state machine (isRunning flag)
 * - Completion flush (plain append, no smooth reveal)
 * - Markdown rendering via StreamdownTextPrimitive
 * - Thread list management
 */

import {
  type ExternalStoreAdapter,
  type ThreadMessage,
  type AppendMessage,
  type ExternalThreadQueueAdapter,
  fromThreadMessageLike,
} from "@assistant-ui/react";

// Internal message representation (simple plain objects)
interface RawMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: Array<{ type: "text"; text: string }>;
  createdAt: Date;
}

const COMPLETE_STATUS = { type: "complete" as const, reason: "stop" as const };
const RUNNING_STATUS = { type: "running" as const } as const;

// Convert internal message to ThreadMessage
function toThreadMessage(m: RawMessage, isRunning: boolean): ThreadMessage {
  // Last assistant message gets RUNNING_STATUS while streaming
  const status = (isRunning && m.role === "assistant")
    ? RUNNING_STATUS
    : COMPLETE_STATUS;

  return fromThreadMessageLike(
    {
      id: m.id,
      role: m.role,
      content: m.content,
      createdAt: m.createdAt,
    },
    m.id,
    status
  );
}

// Adapter
export class TektosExternalStoreAdapter implements ExternalStoreAdapter<ThreadMessage> {
  private _messages: RawMessage[] = [];
  private _isRunning = false;
  private _onNewFn: ((message: AppendMessage) => Promise<void>) | undefined;
  private _onCancelFn: (() => Promise<void>) | undefined;
  private _subscribers: Array<() => void> = [];
  private _version = 0;

  get messages(): readonly ThreadMessage[] {
    const msgs = this._messages.map((m, idx, arr) => {
      // Only the LAST assistant message gets RUNNING_STATUS while streaming
      const isLastAssistant = m.role === "assistant" && idx === arr.length - 1;
      const isRunning = this._isRunning && isLastAssistant;
      return toThreadMessage(m, isRunning);
    });
    // Always return a new array reference so the runtime detects changes
    return [...msgs];
  }

  get version(): number {
    return this._version;
  }

  get isRunning(): boolean {
    return this._isRunning;
  }

  set isRunning(value: boolean) {
    if (this._isRunning !== value) {
      this._isRunning = value;
      this.notify();
    }
  }

  get isLoading(): undefined { return undefined; }
  get isDisabled(): undefined { return undefined; }
  get isSendDisabled(): undefined { return undefined; }
  get suggestions(): readonly never[] { return Object.freeze([]) as readonly never[]; }
  get state(): undefined { return undefined; }
  get extras(): undefined { return undefined; }
  get queue(): ExternalThreadQueueAdapter | undefined { return undefined; }
  get onEdit() { return undefined; }
  get onDelete() { return undefined; }
  get onReload() { return undefined; }
  get onResume() { return undefined; }
  get onAddToolResult() { return undefined; }
  get onImport() { return undefined; }
  get onExportExternalState() { return undefined; }
  get onLoadExternalState() { return undefined; }
  get adapters() { return undefined; }
  get convertMessage() { return undefined; }
  get unstable_onBranchChange() { return undefined; }
  get unstable_capabilities() { return undefined; }
  get messageRepository() { return undefined; }

  get onNew(): (message: AppendMessage) => Promise<void> {
    return this._onNewFn ?? ((_m) => Promise.resolve());
  }

  get onCancel(): () => Promise<void> {
    return this._onCancelFn ?? (() => Promise.resolve());
  }

  set onNew(fn: ((message: AppendMessage) => Promise<void>) | undefined) {
    this._onNewFn = fn;
  }

  set onCancel(fn: (() => Promise<void>) | undefined) {
    this._onCancelFn = fn;
  }

  /** Send a user message, create assistant slot, return assistant msg id */
  async sendMessage(text: string): Promise<string> {
    const userMsg: RawMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: [{ type: "text", text }],
      createdAt: new Date(Date.now()),
    };
    this._messages.push(userMsg);
    this.notify();

    // Create empty assistant message (will be filled by deltas)
    const assistantMsg: RawMessage = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: [],
      createdAt: new Date(Date.now()),
    };
    this._messages.push(assistantMsg);
    this._isRunning = true;
    this.notify();

    // Notify runtime
    await this._onNewFn?.({
      role: "user",
      content: [{ type: "text", text }],
      createdAt: new Date(),
    } as unknown as AppendMessage);

    return assistantMsg.id;
  }

  /** Append text delta to current assistant message */
  addDelta(text: string) {
    const last = this._messages[this._messages.length - 1];
    if (!last || last.role !== "assistant") return;

    if (last.content.length === 0) {
      last.content.push({ type: "text", text });
    } else {
      const textPart = last.content[0] as { type: "text"; text: string };
      if (textPart.type === "text") {
        textPart.text += text;
      }
    }
    this._version++;
    this.notify();
  }

  /** Complete current assistant message */
  completeMessage() {
    this._isRunning = false;
    this._version++;
    this.notify();
  }

  /** Interrupt current response */
  interrupt() {
    this._isRunning = false;
    this._onCancelFn?.();
    this._version++;
  }

  /** Clear all messages */
  clear() {
    this._messages = [];
    this._isRunning = false;
    this._version++;
    this.notify();
  }

  /** Load historical messages from session */
  loadMessages(msgs: RawMessage[]) {
    this._messages = msgs;
    this._isRunning = false;
    this._version++;
    this.notify();
  }

  /** Copy state from another adapter (for identity swap) */
  _copyFrom(other: TektosExternalStoreAdapter) {
    this._messages = [...other._messages];
    this._isRunning = other._isRunning;
    this._version = other._version;
    this._onNewFn = other._onNewFn;
    this._onCancelFn = other._onCancelFn;
  }

  // Subscribe
  subscribe(listener: () => void): () => void {
    this._subscribers.push(listener);
    return () => {
      this._subscribers = this._subscribers.filter((l) => l !== listener);
    };
  }

  private notify() {
    for (const listener of this._subscribers) {
      listener();
    }
  }
}


/**
 * Adapter wrapper that provides a new object identity on each creation
 * while delegating all reads to the underlying adapter.
 * This forces @assistant-ui/react's runtime to re-read fresh messages
 * because __internal_setAdapter sees a different object reference.
 */
export class TektosExternalStoreAdapterWrapper implements ExternalStoreAdapter<ThreadMessage> {
  private readonly _adapter: TektosExternalStoreAdapter;
  
  constructor(adapter: TektosExternalStoreAdapter) {
    this._adapter = adapter;
  }

  // Always delegate to the underlying adapter — reads fresh data
  get messages(): readonly ThreadMessage[] {
    return this._adapter.messages;
  }
  
  get version(): number {
    return this._adapter.version;
  }
  
  get isRunning(): boolean {
    return this._adapter.isRunning;
  }
  
  set isRunning(value: boolean) {
    this._adapter.isRunning = value;
  }
  
  get isLoading(): undefined { return undefined; }
  get isDisabled(): undefined { return undefined; }
  get isSendDisabled(): undefined { return undefined; }
  get suggestions(): readonly never[] { return Object.freeze([]) as readonly never[]; }
  get state(): undefined { return undefined; }
  get extras(): undefined { return undefined; }
  get queue(): ExternalThreadQueueAdapter | undefined { return undefined; }
  get onEdit() { return undefined; }
  get onDelete() { return undefined; }
  get onReload() { return undefined; }
  get onResume() { return undefined; }
  get onAddToolResult() { return undefined; }
  get onImport() { return undefined; }
  get onExportExternalState() { return undefined; }
  get onLoadExternalState() { return undefined; }
  get adapters() { return undefined; }
  get convertMessage() { return undefined; }
  get unstable_onBranchChange() { return undefined; }
  get unstable_capabilities() { return undefined; }
  get messageRepository() { return undefined; }

  get onNew(): (message: AppendMessage) => Promise<void> {
    return this._adapter.onNew;
  }
  
  get onCancel(): () => Promise<void> {
    return this._adapter.onCancel;
  }
  
  set onNew(fn: ((message: AppendMessage) => Promise<void>) | undefined) {
    this._adapter.onNew = fn;
  }
  
  set onCancel(fn: (() => Promise<void>) | undefined) {
    this._adapter.onCancel = fn;
  }
  
  subscribe(listener: () => void): () => void {
    return this._adapter.subscribe(listener);
  }
}
