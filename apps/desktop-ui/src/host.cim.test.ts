import { describe, expect, it, vi } from "vitest";
import {
  createE2EHost,
  createNativeAppHost,
  createTauriHost,
  encodeHostPathHeader,
  pickDirectoryViaCimShell,
} from "./host";

describe("CIM folder picker", () => {
  it("uses the dialog plugin when custom choose_file is blocked", async () => {
    const invoke = vi.fn(async (cmd: string) => {
      if (cmd === "plugin:dialog|open") return "C:\\data\\capsule";
      throw new Error("choose_file not allowed. Plugin not found");
    });
    (window as unknown as { __TAURI_INTERNALS__: { invoke: typeof invoke } }).__TAURI_INTERNALS__ = {
      invoke,
    };
    await expect(pickDirectoryViaCimShell()).resolves.toBe("C:\\data\\capsule");
    expect(invoke).toHaveBeenCalledWith(
      "plugin:dialog|open",
      expect.objectContaining({ directory: true }),
    );
  });

  it("falls back to cimHost.chooseFile when the dialog plugin is missing", async () => {
    (window as unknown as { __TAURI_INTERNALS__: { invoke: (cmd: string) => Promise<unknown> } }).__TAURI_INTERNALS__ =
      {
        invoke: async () => {
          throw new Error("plugin:dialog|open not allowed");
        },
      };
    (window as unknown as { cimHost: { chooseFile: () => Promise<{ canceled: boolean; paths: string[] }> } }).cimHost =
      {
        chooseFile: async () => ({ canceled: false, paths: ["D:\\out"] }),
      };
    await expect(pickDirectoryViaCimShell()).resolves.toBe("D:\\out");
  });

  it("uses the public same-origin NativeApp proxy with the launch secret in a header", async () => {
    const dataset = "C:\\資料\\capsule";
    const launchSecret = "nativeapp-test-secret";
    const chooseFile = vi.fn(async () => ({ canceled: false, paths: [dataset] }));
    const hostWindow = window as unknown as {
      cimHost?: { chooseFile: typeof chooseFile };
      NATIVEAPP_LOCAL_API?: string;
      __TAURI_INTERNALS__?: unknown;
      __TAURI__?: unknown;
    };
    const previous = {
      cimHost: hostWindow.cimHost,
      localApi: hostWindow.NATIVEAPP_LOCAL_API,
      tauriInternals: hostWindow.__TAURI_INTERNALS__,
      tauri: hostWindow.__TAURI__,
    };
    delete hostWindow.__TAURI_INTERNALS__;
    delete hostWindow.__TAURI__;
    hostWindow.NATIVEAPP_LOCAL_API = "";
    hostWindow.cimHost = { chooseFile };
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify({ ready: true, setup_state: "ready" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    try {
      const host = createNativeAppHost(launchSecret);
      await expect(host.pickerOpenFolder("dataset")).resolves.toEqual({
        grant_id: "dataset",
        display_name: "capsule",
      });
      await host.engineHealth();

      expect(chooseFile).toHaveBeenCalledWith({ properties: ["openDirectory"] });
      expect(String(fetchMock.mock.calls[0]?.[0])).toBe(`${window.location.origin}/v1/health`);
      expect(String(fetchMock.mock.calls[0]?.[0])).not.toContain(launchSecret);
      const headers = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>;
      expect(headers["X-SegVision-Launch-Secret"]).toBe(launchSecret);
      expect(headers["X-SegVision-Resolved-Path"]).toBe(encodeHostPathHeader(dataset));
    } finally {
      vi.unstubAllGlobals();
      if (previous.cimHost === undefined) delete hostWindow.cimHost;
      else hostWindow.cimHost = previous.cimHost;
      if (previous.localApi === undefined) delete hostWindow.NATIVEAPP_LOCAL_API;
      else hostWindow.NATIVEAPP_LOCAL_API = previous.localApi;
      if (previous.tauriInternals === undefined) delete hostWindow.__TAURI_INTERNALS__;
      else hostWindow.__TAURI_INTERNALS__ = previous.tauriInternals;
      if (previous.tauri === undefined) delete hostWindow.__TAURI__;
      else hostWindow.__TAURI__ = previous.tauri;
    }
  });

  it("percent-encodes non-ASCII folder paths so fetch can send them", async () => {
    const dataset = "C:\\資料\\capsule";
    const output = "C:\\輸出";
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify({ ready: true, setup_state: "ready" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    try {
      const host = createE2EHost("http://127.0.0.1:9", "secret", dataset, output);
      await host.engineHealth();
      const headers = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>;
      expect(headers["X-SegVision-Resolved-Path"]).toBe(encodeHostPathHeader(dataset));
      expect(headers["X-SegVision-Output-Path"]).toBe(encodeHostPathHeader(output));
      expect(headers["X-SegVision-Resolved-Path"]).toMatch(/^[\x00-\x7F]*$/);
      expect(headers["X-SegVision-Output-Path"]).toMatch(/^[\x00-\x7F]*$/);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("URL-encodes cursors when listing the next sidecar page", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) =>
      new Response(JSON.stringify({ items: [], next_cursor: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    try {
      const host = createE2EHost("http://127.0.0.1:9", "secret", "", "");
      await host.datasetsListItems("dataset-1", "page/2 + next");
      expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
        "http://127.0.0.1:9/v1/datasets/dataset-1/items?cursor=page%2F2%20%2B%20next",
      );
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("posts prompt and frozen-region mutations to the desktop API", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify({ protocol_session_id: "s1", revision: 2 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    try {
      const host = createE2EHost("http://127.0.0.1:9", "secret", "", "");
      await host.sessionsDeletePrompt("s1", 1, "p1");
      await host.sessionsLockRegion("s1", 2, 30, 40, true);
      await host.sessionsUnlockRegion("s1", 3, "r1");
      await host.sessionsStartNextRegion("s1", 4);

      expect(fetchMock.mock.calls.map((call) => String(call[0]))).toEqual([
        "http://127.0.0.1:9/v1/sessions/s1/prompts/delete",
        "http://127.0.0.1:9/v1/sessions/s1/regions/lock",
        "http://127.0.0.1:9/v1/sessions/s1/regions/unlock",
        "http://127.0.0.1:9/v1/sessions/s1/regions/next",
      ]);
      const bodies = fetchMock.mock.calls.map((call) =>
        JSON.parse(String(call[1]?.body)) as Record<string, unknown>,
      );
      expect(bodies[0]).toMatchObject({ base_revision: 1, prompt_id: "p1" });
      expect(bodies[1]).toMatchObject({ base_revision: 2, x: 30, y: 40, guard: true });
      expect(bodies[2]).toMatchObject({ base_revision: 3, region_id: "r1" });
      expect(bodies[3]).toMatchObject({ base_revision: 4 });
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("invokes the matching Tauri commands for prompt and region mutations", async () => {
    const invoke = vi.fn(async (_cmd: string, _args?: Record<string, unknown>) => ({
      protocol_session_id: "s1",
      revision: 2,
    }));
    (window as unknown as { __TAURI_INTERNALS__: { invoke: typeof invoke } }).__TAURI_INTERNALS__ = {
      invoke,
    };
    const host = createTauriHost();

    await host.sessionsDeletePrompt("s1", 1, "p1");
    await host.sessionsLockRegion("s1", 2, 30, 40, true);
    await host.sessionsUnlockRegion("s1", 3, "r1");
    await host.sessionsStartNextRegion("s1", 4);

    expect(invoke.mock.calls.map((call) => call[0])).toEqual([
      "sessions_delete_prompt",
      "sessions_lock_region",
      "sessions_unlock_region",
      "sessions_start_next_region",
    ]);
    expect(invoke.mock.calls[1]?.[1]).toMatchObject({
      sessionId: "s1",
      baseRevision: 2,
      x: 30,
      y: 40,
      guard: true,
    });
  });

  it("passes dataset cursors through the native host command", async () => {
    const invoke = vi.fn(async (_command: string, _args?: Record<string, unknown>) => ({ items: [], next_cursor: null }));
    (window as unknown as { __TAURI_INTERNALS__: { invoke: typeof invoke } }).__TAURI_INTERNALS__ = {
      invoke,
    };
    const host = createTauriHost();

    await host.datasetsListItems("dataset-1", "32");

    expect(invoke).toHaveBeenCalledWith("datasets_list_items", {
      datasetId: "dataset-1",
      cursor: "32",
    });
  });
});
