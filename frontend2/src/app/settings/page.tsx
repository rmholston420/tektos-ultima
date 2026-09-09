"use client";

/**
 * Settings destination. Keybind editor lands in Phase 7. Other settings
 * (theme, model preference) follow.
 */
export default function SettingsPage() {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-auto scrollbar-thin bg-surface-1">
      <div className="hairline px-4 py-3">
        <h1 className="text-14 font-medium text-text-base">Settings</h1>
      </div>
      <div className="p-4 text-12 text-text-muted">
        Keybind editor and theme controls land in Phase 7. Sessions can be
        reset from the Chat destination.
      </div>
    </div>
  );
}
