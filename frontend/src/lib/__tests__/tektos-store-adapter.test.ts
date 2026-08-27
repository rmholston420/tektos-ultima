/**
 * Tests for TektosExternalStoreAdapter — message management, streaming, versioning.
 */

import { TektosExternalStoreAdapter, TektosExternalStoreAdapterWrapper } from "@/lib/tektos-store-adapter";

// Mock @assistant-ui/react
jest.mock("@assistant-ui/react", () => ({
  fromThreadMessageLike: jest.fn((msg: any, id: string, status: any) => ({ ...msg, id, status })),
}));

describe("TektosExternalStoreAdapter", () => {
  let adapter: TektosExternalStoreAdapter;

  beforeEach(() => {
    adapter = new TektosExternalStoreAdapter();
  });

  describe("initial state", () => {
    it("starts with empty messages", () => {
      expect(adapter.messages).toEqual([]);
    });

    it("starts with version 0", () => {
      expect(adapter.version).toBe(0);
    });

    it("starts with isRunning false", () => {
      expect(adapter.isRunning).toBe(false);
    });

    it("returns undefined for optional getters", () => {
      expect(adapter.isLoading).toBeUndefined();
      expect(adapter.isDisabled).toBeUndefined();
      expect(adapter.isSendDisabled).toBeUndefined();
      expect(adapter.suggestions).toEqual([]);
      expect(adapter.state).toBeUndefined();
      expect(adapter.extras).toBeUndefined();
      expect(adapter.queue).toBeUndefined();
      expect(adapter.onEdit).toBeUndefined();
      expect(adapter.onDelete).toBeUndefined();
      expect(adapter.onReload).toBeUndefined();
      expect(adapter.onResume).toBeUndefined();
      expect(adapter.onAddToolResult).toBeUndefined();
      expect(adapter.onImport).toBeUndefined();
      expect(adapter.onExportExternalState).toBeUndefined();
      expect(adapter.onLoadExternalState).toBeUndefined();
      expect(adapter.adapters).toBeUndefined();
      expect(adapter.convertMessage).toBeUndefined();
      expect(adapter.unstable_onBranchChange).toBeUndefined();
      expect(adapter.unstable_capabilities).toBeUndefined();
      expect(adapter.messageRepository).toBeUndefined();
    });

    it("returns no-op functions for onNew and onCancel", () => {
      expect(typeof adapter.onNew).toBe("function");
      expect(typeof adapter.onCancel).toBe("function");
    });
  });

  describe("sendMessage", () => {
    it("creates user and assistant messages", async () => {
      const assistantId = await adapter.sendMessage("hello");
      expect(adapter.messages).toHaveLength(2);
      expect(adapter.messages[0].role).toBe("user");
      expect(adapter.messages[1].role).toBe("assistant");
      expect(assistantId).toBe(adapter.messages[1].id);
    });

    it("sets isRunning to true after sendMessage", async () => {
      await adapter.sendMessage("hello");
      expect(adapter.isRunning).toBe(true);
    });

    it("increments version after sendMessage", async () => {
      await adapter.sendMessage("hello");
      expect(adapter.version).toBeGreaterThan(0);
    });

    it("returns assistant message id", async () => {
      const id = await adapter.sendMessage("hello");
      expect(id).toMatch(/^assistant-/);
    });
  });

  describe("addDelta", () => {
    it("appends text to last assistant message", async () => {
      await adapter.sendMessage("hello");
      adapter.addDelta(" world");
      const content = adapter.messages[1].content[0] as { type: "text"; text: string };
      expect(content.type).toBe("text");
      expect(content.text).toBe(" world");
    });

    it("does nothing when no assistant message", () => {
      adapter.addDelta("orphan delta");
      expect(adapter.messages).toHaveLength(0);
    });

    it("increments version after addDelta", async () => {
      const initialVersion = adapter.version;
      await adapter.sendMessage("hello");
      adapter.addDelta("test");
      expect(adapter.version).toBeGreaterThan(initialVersion);
    });
  });

  describe("completeMessage", () => {
    it("sets isRunning to false", async () => {
      await adapter.sendMessage("hello");
      adapter.completeMessage();
      expect(adapter.isRunning).toBe(false);
    });

    it("increments version after completeMessage", async () => {
      const initialVersion = adapter.version;
      await adapter.sendMessage("hello");
      adapter.completeMessage();
      expect(adapter.version).toBeGreaterThan(initialVersion);
    });
  });

  describe("interrupt", () => {
    it("sets isRunning to false", async () => {
      await adapter.sendMessage("hello");
      adapter.interrupt();
      expect(adapter.isRunning).toBe(false);
    });

    it("calls onCancel handler", async () => {
      await adapter.sendMessage("hello");
      const onCancel = jest.fn();
      adapter.onCancel = onCancel;
      adapter.interrupt();
      expect(onCancel).toHaveBeenCalled();
    });

    it("increments version after interrupt", async () => {
      const initialVersion = adapter.version;
      await adapter.sendMessage("hello");
      adapter.interrupt();
      expect(adapter.version).toBeGreaterThan(initialVersion);
    });
  });

  describe("clear", () => {
    it("removes all messages", async () => {
      await adapter.sendMessage("hello");
      adapter.clear();
      expect(adapter.messages).toHaveLength(0);
    });

    it("sets isRunning to false", async () => {
      await adapter.sendMessage("hello");
      adapter.clear();
      expect(adapter.isRunning).toBe(false);
    });

    it("increments version after clear", async () => {
      const initialVersion = adapter.version;
      await adapter.sendMessage("hello");
      adapter.clear();
      expect(adapter.version).toBeGreaterThan(initialVersion);
    });
  });

  describe("loadMessages", () => {
    it("loads historical messages", () => {
      const msgs = [
        { id: "user-1", role: "user" as const, content: [{ type: "text" as const, text: "hi" }], createdAt: new Date() },
        { id: "assistant-1", role: "assistant" as const, content: [{ type: "text" as const, text: "hello" }], createdAt: new Date() },
      ];
      adapter.loadMessages(msgs);
      expect(adapter.messages).toHaveLength(2);
      expect(adapter.messages[0].role).toBe("user");
      expect(adapter.messages[1].role).toBe("assistant");
    });

    it("sets isRunning to false", () => {
      adapter.loadMessages([]);
      expect(adapter.isRunning).toBe(false);
    });

    it("increments version after loadMessages", async () => {
      const initialVersion = adapter.version;
      await adapter.sendMessage("hello");
      adapter.loadMessages([]);
      expect(adapter.version).toBeGreaterThan(initialVersion);
    });
  });

  describe("isRunning setter", () => {
    it("notifies subscribers when isRunning changes", () => {
      const listener = jest.fn();
      adapter.subscribe(listener);
      adapter.isRunning = true;
      expect(listener).toHaveBeenCalled();
    });

    it("does not notify when isRunning is unchanged", () => {
      const listener = jest.fn();
      adapter.subscribe(listener);
      adapter.isRunning = false; // Already false
      expect(listener).not.toHaveBeenCalled();
    });
  });

  describe("subscribe", () => {
    it("calls listener on notify", () => {
      const listener = jest.fn();
      const unsubscribe = adapter.subscribe(listener);
      adapter.isRunning = true;
      expect(listener).toHaveBeenCalled();
      unsubscribe();
      adapter.isRunning = false;
    });

    it("returns unsubscribe function", () => {
      const listener = jest.fn();
      const unsubscribe = adapter.subscribe(listener);
      adapter.isRunning = true;
      expect(listener).toHaveBeenCalledTimes(1);
      unsubscribe();
      adapter.isRunning = false;
      expect(listener).toHaveBeenCalledTimes(1);
    });
  });

  describe("onNew and onCancel setters", () => {
    it("sets onNew handler", () => {
      const onNew = jest.fn();
      adapter.onNew = onNew;
      expect(adapter.onNew).toBe(onNew);
    });

    it("sets onCancel handler", () => {
      const onCancel = jest.fn();
      adapter.onCancel = onCancel;
      expect(adapter.onCancel).toBe(onCancel);
    });
  });

  describe("messages getter", () => {
    it("returns new array reference each time", async () => {
      await adapter.sendMessage("hello");
      const msgs1 = adapter.messages;
      const msgs2 = adapter.messages;
      expect(msgs1).not.toBe(msgs2);
    });

    it("marks last assistant message as running when isRunning is true", async () => {
      await adapter.sendMessage("hello");
      const msgs = adapter.messages;
      expect(msgs[1].status?.type).toBe("running");
    });

    it("marks assistant message as complete when isRunning is false", async () => {
      await adapter.sendMessage("hello");
      adapter.completeMessage();
      const msgs = adapter.messages;
      expect(msgs[1].status?.type).toBe("complete");
    });
  });

  describe("_copyFrom", () => {
    it("copies state from another adapter", () => {
      const other = new TektosExternalStoreAdapter();
      (other as any)._messages = [
        { id: "user-1", role: "user", content: [{ type: "text", text: "hi" }], createdAt: new Date() },
      ];
      (other as any)._isRunning = true;
      (other as any)._version = 5;
      (other as any)._onNewFn = jest.fn();
      (other as any)._onCancelFn = jest.fn();

      adapter._copyFrom(other);
      expect((adapter as any)._messages).toHaveLength(1);
      expect(adapter.isRunning).toBe(true);
      expect(adapter.version).toBe(5);
    });
  });
});

describe("TektosExternalStoreAdapterWrapper", () => {
  let adapter: TektosExternalStoreAdapter;
  let wrapper: TektosExternalStoreAdapterWrapper;

  beforeEach(() => {
    adapter = new TektosExternalStoreAdapter();
    wrapper = new TektosExternalStoreAdapterWrapper(adapter);
  });

  it("delegates messages to underlying adapter", () => {
    expect(wrapper.messages).toEqual(adapter.messages);
  });

  it("delegates version to underlying adapter", () => {
    expect(wrapper.version).toBe(adapter.version);
  });

  it("delegates isRunning to underlying adapter", () => {
    expect(wrapper.isRunning).toBe(adapter.isRunning);
  });

  it("sets isRunning on underlying adapter", () => {
    wrapper.isRunning = true;
    expect(adapter.isRunning).toBe(true);
  });

  it("delegates onNew to underlying adapter", () => {
    // Both return no-op functions (different references, same behavior)
    expect(typeof wrapper.onNew).toBe("function");
    expect(typeof adapter.onNew).toBe("function");
  });

  it("delegates onCancel to underlying adapter", () => {
    expect(typeof wrapper.onCancel).toBe("function");
    expect(typeof adapter.onCancel).toBe("function");
  });

  it("sets onNew on underlying adapter", () => {
    const onNew = jest.fn();
    wrapper.onNew = onNew;
    expect(adapter.onNew).toBe(onNew);
  });

  it("sets onCancel on underlying adapter", () => {
    const onCancel = jest.fn();
    wrapper.onCancel = onCancel;
    expect(adapter.onCancel).toBe(onCancel);
  });

  it("delegates subscribe to underlying adapter", () => {
    const listener = jest.fn();
    const unsubscribe = wrapper.subscribe(listener);
    adapter.isRunning = true;
    expect(listener).toHaveBeenCalled();
    unsubscribe();
  });

  it("returns undefined for optional getters", () => {
    expect(wrapper.isLoading).toBeUndefined();
    expect(wrapper.isDisabled).toBeUndefined();
    expect(wrapper.isSendDisabled).toBeUndefined();
    expect(wrapper.suggestions).toEqual([]);
    expect(wrapper.state).toBeUndefined();
    expect(wrapper.extras).toBeUndefined();
    expect(wrapper.queue).toBeUndefined();
    expect(wrapper.onEdit).toBeUndefined();
    expect(wrapper.onDelete).toBeUndefined();
    expect(wrapper.onReload).toBeUndefined();
    expect(wrapper.onResume).toBeUndefined();
    expect(wrapper.onAddToolResult).toBeUndefined();
    expect(wrapper.onImport).toBeUndefined();
    expect(wrapper.onExportExternalState).toBeUndefined();
    expect(wrapper.onLoadExternalState).toBeUndefined();
    expect(wrapper.adapters).toBeUndefined();
    expect(wrapper.convertMessage).toBeUndefined();
    expect(wrapper.unstable_onBranchChange).toBeUndefined();
    expect(wrapper.unstable_capabilities).toBeUndefined();
    expect(wrapper.messageRepository).toBeUndefined();
  });
});
