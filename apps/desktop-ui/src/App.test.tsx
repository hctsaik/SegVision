import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App, editRegionToCrop, operatorMessage, strokePointsToCrop } from "./App";
import type { HostClient, Snapshot } from "./host";
import { useViewStore } from "./store";

function snap(over: Partial<Snapshot> = {}): Snapshot {
  return {
    protocol_session_id: "s1",
    workflow_state: "PROPOSAL_READY",
    revision: 1,
    class_id: "part",
    candidates: [
      {
        candidate_id: "c1",
        source: "sam_box",
        capabilities: { can_refine: true, can_local_edit: true, can_commit: true },
        mask_token: "m1",
      },
    ],
    warnings: [],
    job: { job_id: null, kind: null, status: null },
    assets: { source_image: null, thumbnail: null, mask: null },
    persist: {},
    controls: { next: false, fusion: false },
    selected_candidate_id: "c1",
    ...over,
  };
}

function host(snapshot: Snapshot): HostClient {
  return {
    engineHealth: vi.fn(async () => ({
      ready: true,
      setup_state: "ready",
      backend: { name: "fake", approved: true },
    })),
    pickerOpenFolder: vi.fn(async (kind) => ({
      grant_id: kind === "output" ? "out" : "g",
      display_name: kind === "output" ? "output" : "ds",
    })),
    datasetsOpen: vi.fn(async () => ({ dataset_id: "d", class_id: "part", item_count: 1 })),
    datasetsListItems: vi.fn(async () => ({
      items: [{ item_id: "i1", image_id: "part", display_name: "part.png", class_id: "part" }],
    })),
    sessionsCreate: vi.fn(async () => snapshot),
    sessionsGet: vi.fn(async () => snapshot),
    sessionsLockRoi: vi.fn(async () => snapshot),
    sessionsPropose: vi.fn(async () => snapshot),
    sessionsSelect: vi.fn(async () => snapshot),
    sessionsClearSelection: vi.fn(async () => snapshot),
    sessionsRefine: vi.fn(async () => snapshot),
    sessionsDeletePrompt: vi.fn(async () => snapshot),
    sessionsLockRegion: vi.fn(async () => snapshot),
    sessionsUnlockRegion: vi.fn(async () => snapshot),
    sessionsStartNextRegion: vi.fn(async () => snapshot),
    sessionsEdit: vi.fn(async () => snapshot),
    sessionsUndo: vi.fn(async () => snapshot),
    sessionsManualEmpty: vi.fn(async () => snapshot),
    sessionsExpandRoi: vi.fn(async () => snapshot),
    sessionsAccept: vi.fn(async () => snapshot),
    sessionsNeedsReview: vi.fn(async () => snapshot),
    sessionsClose: vi.fn(async () => snapshot),
    jobsCancel: vi.fn(async () => ({})),
    loadAsset: async (token: string) => ({ url: `asset://${token}`, revoke: false }),
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("App", () => {
  it("converts full-image brush samples into crop coordinates", () => {
    expect(
      strokePointsToCrop(
        [
          [17, 13],
          [8, 5],
          [99, 99],
        ],
        [8, 5, 40, 25],
      ),
    ).toEqual([
      [9, 8],
      [0, 0],
    ]);
  });

  it("converts a two-point full-image work area into crop coordinates", () => {
    expect(editRegionToCrop([14, 18, 30, 42], [10, 12, 50, 60])).toEqual([4, 6, 20, 30]);
    expect(editRegionToCrop([0, 0, 100, 100], [10, 12, 50, 60])).toEqual([0, 0, 40, 48]);
  });

  it("turns rejected MobileSAM point output into a recoverable Chinese message", () => {
    const error = JSON.stringify({
      code: "validation_failed",
      message: "refinement rejected: POINT_CONSTRAINT_VIOLATION",
    });
    expect(operatorMessage(error)).toContain("已保留上一個遮罩");
    expect(operatorMessage(error)).toContain("換個位置再點一次");
    expect(operatorMessage(error)).not.toContain("POINT_CONSTRAINT_VIOLATION");
  });

  it("opens a dataset without putting raw paths in the store", async () => {
    useViewStore.setState({
      snapshot: null,
      grantId: null,
      datasetId: null,
      items: [],
      currentItemId: null,
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    const client = host(snap({ workflow_state: "IMAGE_OPEN", revision: 0, candidates: [] }));
    render(<App host={client} />);
    await userEvent.click(screen.getByTestId("open-dataset"));
    expect(useViewStore.getState().grantId).toBe("g");
    expect(JSON.stringify(useViewStore.getState())).not.toMatch(/C:\\|\/home\//);
    expect(screen.getByText("part.png")).toBeInTheDocument();
    expect(screen.getByTestId("region-empty")).toHaveTextContent(/點兩個角建立黃框/);
  });

  it("shows sidecar job status from the Tauri snapshot", () => {
    useViewStore.setState({
      snapshot: snap({ job: { job_id: "j1", kind: "propose", status: "running" } }),
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    const client = host(snap());
    render(<App host={client} />);
    expect(screen.getByTestId("job-state")).toHaveAttribute("data-kind", "propose");
    expect(screen.getByTestId("job-state")).toHaveAttribute("data-status", "running");
    expect(screen.getByTestId("job-state")).toHaveTextContent("計算遮罩 進行中");
  });

  it("renders only real candidate cards", () => {
    useViewStore.setState({ snapshot: snap(), uiError: null, outputGrantId: null, outputDisplayName: null });
    render(<App host={host(snap())} />);
    expect(screen.getByTestId("annotation-canvas")).toHaveAttribute("data-user-roi", "");
    expect(screen.getByTestId("viewer-fit")).toBeInTheDocument();
    expect(screen.getByTestId("viewer-frame-roi")).toBeDisabled();
    expect(screen.getByTestId("tool-pan")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-rail")).toBeInTheDocument();
    expect(screen.getByTestId("edit-grow")).toBeDisabled();
    expect(screen.getByTestId("candidate-1")).toHaveTextContent(/選項 1/);
    expect(screen.getByTestId("region-status")).toHaveTextContent(/粉紅/);
    expect(screen.queryByTestId("candidate-2")).toBeNull();
    expect(screen.queryByTestId("candidate-3")).toBeNull();
  });

  it("offers explicit foreground and background MobileSAM point tools", async () => {
    useViewStore.setState({
      snapshot: snap({ controls: { refine: true, local_edit: true, accept: true } }),
      tool: "point",
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    render(<App host={host(snap())} />);

    expect(screen.getByTestId("tool-point")).toHaveTextContent("補選");
    expect(screen.getByTestId("tool-point-remove")).toHaveTextContent("排除");
    await userEvent.click(screen.getByTestId("tool-point-remove"));
    expect(useViewStore.getState().tool).toBe("point-remove");
    expect(screen.getByTestId("tool-point-remove")).toHaveAttribute("aria-pressed", "true");
  });

  it("exposes the SAM two-point box and separate edit-area tool before local editing", async () => {
    const state = snap({
      workflow_state: "IMAGE_OPEN",
      candidates: [],
      selected_candidate_id: null,
      controls: { roi: true, local_edit: false },
    });
    useViewStore.setState({
      snapshot: state,
      tool: "roi",
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    render(<App host={host(state)} />);

    const samButton = screen.getByTestId("tool-roi");
    expect(samButton).toHaveTextContent("框選");
    expect(samButton).not.toBeDisabled();
    const editButton = screen.getByTestId("tool-edit-region");
    expect(editButton).toHaveTextContent("編輯範圍");
    expect(editButton).not.toBeDisabled();
    await userEvent.click(editButton);
    expect(useViewStore.getState().tool).toBe("edit-region");
    expect(screen.getByTestId("two-point-box-instruction")).toHaveTextContent("請點第一個角");
  });

  it("keeps SAM point tools visible with a Chinese reason after manual editing", async () => {
    const state = snap({
      workflow_state: "LOCAL_EDITING",
      controls: { refine: false, local_edit: true },
      candidates: [
        {
          candidate_id: "manual-1",
          source: "manual_edit",
          capabilities: { can_refine: false, can_local_edit: true, can_commit: true },
          mask_token: "manual-mask",
        },
      ],
      selected_candidate_id: "manual-1",
    });
    useViewStore.setState({
      snapshot: state,
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    const client = host(state);
    render(<App host={client} />);

    expect(screen.getByTestId("tool-point")).toBeDisabled();
    expect(screen.getByTestId("tool-point-remove")).toBeDisabled();
    expect(screen.getByTestId("sam-tool-reason")).toHaveTextContent("SAM 點選已暫停");
    expect(screen.getByTestId("sam-tool-reason")).toHaveTextContent("復原");
    await userEvent.click(screen.getByTestId("return-to-sam"));
    await waitFor(() => expect(client.sessionsUndo).toHaveBeenCalledWith("s1", 1));
  });

  it("undoes all consecutive manual strokes before re-enabling SAM", async () => {
    const manual = snap({
      workflow_state: "LOCAL_EDITING",
      controls: { refine: false, local_edit: true },
      candidates: [
        {
          candidate_id: "manual-2",
          source: "manual_edit",
          capabilities: { can_refine: false, can_local_edit: true, can_commit: true },
          mask_token: "manual-mask-2",
        },
      ],
      selected_candidate_id: "manual-2",
    });
    const previous = { ...manual, candidates: [{ ...manual.candidates[0], candidate_id: "manual-1" }], selected_candidate_id: "manual-1" };
    const sam = snap({ controls: { refine: true, local_edit: true } });
    useViewStore.setState({ snapshot: manual, uiError: null, outputGrantId: null, outputDisplayName: null });
    const client = host(manual);
    client.sessionsUndo = vi.fn()
      .mockResolvedValueOnce(previous)
      .mockResolvedValueOnce(sam);
    render(<App host={client} />);

    await userEvent.click(screen.getByTestId("return-to-sam"));
    await waitFor(() => expect(client.sessionsUndo).toHaveBeenCalledTimes(2));
    expect(useViewStore.getState().tool).toBe("point");
  });

  it("offers a true one-pixel pencil option for local repair", async () => {
    useViewStore.setState({
      snapshot: snap({ controls: { refine: true, local_edit: true } }),
      tool: "brush",
      brushRadius: 2,
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    render(<App host={host(snap())} />);

    const pencil = screen.getByTestId("brush-radius-0");
    expect(screen.getByTestId("brush-radius-1")).toHaveTextContent("3px");
    expect(screen.getByTestId("brush-radius-2")).toHaveTextContent("5px");
    expect(pencil).toHaveTextContent("1px 鉛筆");
    await userEvent.click(pencil);
    expect(useViewStore.getState().brushRadius).toBe(0);
  });

  it("selects and deletes a prompt by its authoritative point id", async () => {
    const state = snap({
      controls: { refine: true, local_edit: true, delete_prompt: true },
      prompt_points: [{ point_id: "p-1", x: 31, y: 42, label: 1 }],
    });
    useViewStore.setState({
      snapshot: state,
      selectedPromptId: null,
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    const client = host(state);
    client.sessionsDeletePrompt = vi.fn(async () => ({ ...state, prompt_points: [] }));
    render(<App host={client} />);

    await userEvent.click(screen.getByTestId("prompt-chip-0"));
    expect(useViewStore.getState().selectedPromptId).toBe("p-1");
    await userEvent.click(screen.getByTestId("delete-prompt"));
    await waitFor(() =>
      expect(client.sessionsDeletePrompt).toHaveBeenCalledWith("s1", 1, "p-1"),
    );
  });

  it("wires frozen-region controls to the host", async () => {
    const state = snap({
      controls: { lock_region: true, unlock_region: true, next_region: true, merge_regions: true },
      frozen_regions: [{ region_id: "r-1", label: 1, pixel_count: 25 }],
      pass_index: 2,
    });
    useViewStore.setState({
      snapshot: state,
      tool: "point",
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    const client = host(state);
    client.sessionsLockRegion = vi.fn(async () => state);
    client.sessionsUnlockRegion = vi.fn(async () => ({ ...state, frozen_regions: [] }));
    client.sessionsStartNextRegion = vi.fn(async () => ({ ...state, pass_index: 3 }));
    client.sessionsEdit = vi.fn(async () => state);
    render(<App host={client} />);

    expect(screen.getByTestId("region-work-panel")).toHaveTextContent("已鎖定 1 個區塊");
    expect(screen.getByTestId("region-work-panel")).toHaveTextContent("第 2 輪");
    await userEvent.click(screen.getByTestId("lock-region"));
    expect(useViewStore.getState().tool).toBe("lock-region");
    await userEvent.click(screen.getByTestId("unlock-region"));
    await waitFor(() =>
      expect(client.sessionsUnlockRegion).toHaveBeenCalledWith("s1", 1, "r-1"),
    );
    await userEvent.click(screen.getByTestId("next-region"));
    await waitFor(() => expect(client.sessionsStartNextRegion).toHaveBeenCalled());
    await userEvent.click(screen.getByTestId("merge-regions"));
    await waitFor(() =>
      expect(client.sessionsEdit).toHaveBeenCalledWith("s1", 1, "merge"),
    );
  });

  it("unlocks the Frozen region selected in the Dropbox", async () => {
    const state = snap({
      controls: { lock_region: true, unlock_region: true, next_region: true },
      frozen_regions: [
        { region_id: "r-1", label: 1, pixel_count: 25 },
        { region_id: "r-2", label: 0, pixel_count: 11 },
      ],
    });
    useViewStore.setState({ snapshot: state, uiError: null, outputGrantId: null, outputDisplayName: null });
    const client = host(state);
    client.sessionsUnlockRegion = vi.fn(async () => ({ ...state, frozen_regions: [state.frozen_regions![0]!] }));
    render(<App host={client} />);

    const select = screen.getByTestId("frozen-region-select");
    expect(select).toHaveValue("r-2");
    await userEvent.selectOptions(select, "r-1");
    await userEvent.click(screen.getByTestId("unlock-region"));
    await waitFor(() =>
      expect(client.sessionsUnlockRegion).toHaveBeenCalledWith("s1", 1, "r-1"),
    );
  });

  it("shows repeated crop-edge warnings once in Chinese", () => {
    const warning = {
      code: "TOUCHES_WORK_CROP_EDGE",
      message: "foreground touches the padded work-crop boundary",
    };
    useViewStore.setState({
      snapshot: snap({ warnings: [warning, warning, warning] }),
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    render(<App host={host(snap())} />);

    const list = screen.getByTestId("session-warnings");
    expect(list.children).toHaveLength(1);
    expect(list).toHaveTextContent("遮罩碰到工作區邊界");
    expect(list).not.toHaveTextContent("foreground touches");
  });

  it("switches candidates and can clear the authoritative selection", async () => {
    const secondCandidate = {
      candidate_id: "c2",
      source: "sam_box",
      capabilities: { can_refine: true, can_local_edit: true, can_commit: true },
      mask_token: "m2",
    };
    const initial = snap({ candidates: [...snap().candidates, secondCandidate] });
    useViewStore.setState({
      snapshot: initial,
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    const client = host(initial);
    client.sessionsSelect = vi.fn(async (_session, _revision, candidateId) =>
      snap({ candidates: initial.candidates, selected_candidate_id: candidateId }),
    );
    client.sessionsClearSelection = vi.fn(async () =>
      snap({
        candidates: initial.candidates,
        selected_candidate_id: null,
        controls: { accept: false, refine: false, local_edit: false },
      }),
    );
    render(<App host={client} />);

    await userEvent.click(screen.getByTestId("candidate-2"));
    await waitFor(() =>
      expect(useViewStore.getState().snapshot?.selected_candidate_id).toBe("c2"),
    );
    expect(client.sessionsSelect).toHaveBeenCalledWith("s1", 1, "c2");

    await userEvent.click(screen.getByTestId("cancel-candidate-selection"));
    await waitFor(() =>
      expect(useViewStore.getState().snapshot?.selected_candidate_id).toBeNull(),
    );
    expect(client.sessionsClearSelection).toHaveBeenCalledWith("s1", 1);
    expect(screen.queryByTestId("cancel-candidate-selection")).toBeNull();
  });

  it("disables next until durable outcome", () => {
    useViewStore.setState({
      snapshot: snap({ controls: { next: false } }),
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    render(<App host={host(snap())} />);
    expect(screen.getByTestId("next-image")).toBeDisabled();
  });

  it("shows a recoverable error when dataset opening fails", async () => {
    useViewStore.setState({
      snapshot: null,
      uiError: null,
      items: [],
      currentItemId: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    const client = host(snap());
    client.pickerOpenFolder = vi.fn(async () => {
      throw JSON.stringify({ code: "grant_invalid", message: "folder access was cancelled" });
    });
    render(<App host={client} />);
    await userEvent.click(screen.getByTestId("open-dataset"));
    expect(await screen.findByRole("alert")).toHaveTextContent(/沒有選擇資料夾/);
  });

  it("opens the folder picker from Accept when no grant is set", async () => {
    useViewStore.setState({
      snapshot: snap({ controls: { accept: true, needs_review: true, next: false } }),
      outputGrantId: null,
      outputDisplayName: null,
      uiError: null,
    });
    const client = host(snap());
    client.sessionsAccept = vi.fn(async () => snap({ workflow_state: "ACCEPTED" }));
    render(<App host={client} />);

    expect(screen.getByTestId("accept")).toBeEnabled();
    expect(screen.getByTestId("save-bar")).toHaveTextContent(/先選資料夾/);
    await userEvent.click(screen.getByTestId("accept"));

    await waitFor(() => expect(client.pickerOpenFolder).toHaveBeenCalledWith("output"));
    await waitFor(() =>
      expect(client.sessionsAccept).toHaveBeenCalledWith("s1", 1, [], "out", false),
    );
  });

  it("does not Accept when the folder picker is cancelled", async () => {
    useViewStore.setState({
      snapshot: snap({ controls: { accept: true, needs_review: true, next: false } }),
      outputGrantId: null,
      outputDisplayName: null,
      uiError: null,
    });
    const client = host(snap());
    client.pickerOpenFolder = vi.fn(async () => {
      throw JSON.stringify({ code: "grant_invalid", message: "folder access was cancelled" });
    });
    client.sessionsAccept = vi.fn(async () => snap({ workflow_state: "ACCEPTED" }));
    render(<App host={client} />);
    await userEvent.click(screen.getByTestId("save-bar-accept"));
    expect(await screen.findByRole("alert")).toHaveTextContent(/沒有選擇資料夾/);
    expect(client.sessionsAccept).not.toHaveBeenCalled();
  });

  it("removes host-private persistence paths before storing a snapshot", () => {
    const privatePath = "C:\\private-output\\part.json";
    useViewStore.getState().applySnapshot({
      ...snap(),
      persist: {
        kind: "accepted",
        training_eligible: true,
        path: privatePath,
      } as unknown as Snapshot["persist"],
    });

    expect(JSON.stringify(useViewStore.getState())).not.toContain(privatePath);
  });

  it("discards an older image-open response after a faster item switch", async () => {
    useViewStore.setState({
      snapshot: null,
      grantId: null,
      datasetId: null,
      items: [],
      currentItemId: null,
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    const first = deferred<Snapshot>();
    const second = deferred<Snapshot>();
    const client = host(snap());
    client.datasetsListItems = vi.fn(async () => ({
      items: [
        { item_id: "i1", image_id: "first", display_name: "first.png", class_id: "part" },
        { item_id: "i2", image_id: "second", display_name: "second.png", class_id: "part" },
      ],
    }));
    client.sessionsCreate = vi.fn((_datasetId, itemId) =>
      itemId === "i1" ? first.promise : second.promise,
    );
    render(<App host={client} />);

    await userEvent.click(screen.getByTestId("open-dataset"));
    await userEvent.click(screen.getByText("first.png"));
    await userEvent.click(screen.getByText("second.png"));

    await act(async () => second.resolve(snap({ protocol_session_id: "s2", revision: 0 })));
    await waitFor(() => expect(useViewStore.getState().snapshot?.protocol_session_id).toBe("s2"));
    await act(async () => first.resolve(snap({ protocol_session_id: "s1", revision: 0 })));

    await waitFor(() => {
      expect(useViewStore.getState().currentItemId).toBe("i2");
      expect(useViewStore.getState().snapshot?.protocol_session_id).toBe("s2");
    });
  });

  it("discards a mutation response when the user switches to another image", async () => {
    const mutation = deferred<Snapshot>();
    const second = deferred<Snapshot>();
    useViewStore.setState({
      snapshot: snap({ protocol_session_id: "s1", revision: 1 }),
      grantId: "g",
      datasetId: "d",
      items: [
        { item_id: "i1", image_id: "first", display_name: "first.png", class_id: "part" },
        { item_id: "i2", image_id: "second", display_name: "second.png", class_id: "part" },
      ],
      currentItemId: "i1",
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    const client = host(snap());
    client.sessionsSelect = vi.fn(() => mutation.promise);
    client.sessionsCreate = vi.fn(() => second.promise);
    render(<App host={client} />);

    await userEvent.click(screen.getByTestId("candidate-1"));
    await userEvent.click(screen.getByText("second.png"));
    await act(async () => second.resolve(snap({ protocol_session_id: "s2", revision: 0 })));
    await waitFor(() => expect(useViewStore.getState().snapshot?.protocol_session_id).toBe("s2"));
    await act(async () => mutation.resolve(snap({ protocol_session_id: "s1", revision: 2 })));

    await waitFor(() => expect(useViewStore.getState().snapshot?.protocol_session_id).toBe("s2"));
  });

  it("serializes mutations so each request uses the newest authoritative revision", async () => {
    const first = deferred<Snapshot>();
    const second = deferred<Snapshot>();
    useViewStore.setState({
      snapshot: snap({ protocol_session_id: "s1", revision: 1 }),
      grantId: "g",
      datasetId: "d",
      items: [],
      currentItemId: "i1",
      uiError: null,
      outputGrantId: null,
      outputDisplayName: null,
    });
    const client = host(snap());
    client.sessionsSelect = vi
      .fn()
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise);
    render(<App host={client} />);

    await userEvent.click(screen.getByTestId("candidate-1"));
    await userEvent.click(screen.getByTestId("candidate-1"));
    await waitFor(() => expect(client.sessionsSelect).toHaveBeenCalledTimes(1));
    expect(client.sessionsSelect).toHaveBeenLastCalledWith("s1", 1, "c1");

    await act(async () => first.resolve(snap({ protocol_session_id: "s1", revision: 2 })));
    await waitFor(() => expect(client.sessionsSelect).toHaveBeenCalledTimes(2));
    expect(client.sessionsSelect).toHaveBeenLastCalledWith("s1", 2, "c1");
    await act(async () => second.resolve(snap({ protocol_session_id: "s1", revision: 3 })));

    await waitFor(() => expect(useViewStore.getState().snapshot?.revision).toBe(3));
  });

  it("closes the previous authoritative session before opening the next image", async () => {
    useViewStore.setState({
      snapshot: snap({ controls: { next: true }, user_roi_full: [10, 10, 40, 40] }),
      grantId: "g",
      datasetId: "d",
      items: [
        { item_id: "i1", image_id: "first", display_name: "first.png", class_id: "part" },
        { item_id: "i2", image_id: "second", display_name: "second.png", class_id: "part" },
      ],
      currentItemId: "i1",
      outputGrantId: null,
      outputDisplayName: null,
      uiError: null,
      reuseLastRoi: false,
    });
    const client = host(snap());
    client.sessionsClose = vi.fn(async () => snap({ candidates: [] }));
    client.sessionsCreate = vi.fn(async () => snap({ protocol_session_id: "s2", revision: 0 }));
    render(<App host={client} />);

    await userEvent.click(screen.getByTestId("next-image"));

    await waitFor(() => {
      expect(client.sessionsClose).toHaveBeenCalledWith("s1", 1);
      expect(client.sessionsCreate).toHaveBeenCalledWith("d", "i2", false);
      expect(useViewStore.getState().snapshot?.protocol_session_id).toBe("s2");
    });
    expect(client.sessionsLockRoi).not.toHaveBeenCalled();
  });

  it("keeps reuse-last-ROI off on a cold launch", () => {
    useViewStore.setState({
      snapshot: null,
      grantId: null,
      datasetId: null,
      items: [],
      currentItemId: null,
      uiError: null,
      reuseLastRoi: false,
    });
    render(<App host={host(snap())} />);
    expect(screen.getByTestId("reuse-last-roi")).not.toBeChecked();
  });

  it("locks the carried ROI after Next when reuse is enabled", async () => {
    useViewStore.setState({
      snapshot: snap({
        controls: { next: true },
        user_roi_full: [10, 20, 110, 90],
        class_id: "part",
      }),
      grantId: "g",
      datasetId: "d",
      items: [
        { item_id: "i1", image_id: "first", display_name: "first.png", class_id: "part" },
        { item_id: "i2", image_id: "second", display_name: "second.png", class_id: "part" },
      ],
      currentItemId: "i1",
      outputGrantId: "out",
      outputDisplayName: "output",
      uiError: null,
      reuseLastRoi: true,
    });
    const created = snap({
      protocol_session_id: "s2",
      revision: 0,
      workflow_state: "IMAGE_OPEN",
      candidates: [],
      user_roi_full: null,
    });
    const locked = snap({
      protocol_session_id: "s2",
      revision: 1,
      workflow_state: "PROPOSAL_READY",
      user_roi_full: [10, 20, 110, 90],
    });
    const client = host(created);
    client.sessionsClose = vi.fn(async () => snap({ candidates: [] }));
    client.sessionsCreate = vi.fn(async () => created);
    client.sessionsLockRoi = vi.fn(async () => locked);
    render(<App host={client} />);

    await userEvent.click(screen.getByTestId("next-image"));

    await waitFor(() => {
      expect(client.sessionsClose).toHaveBeenCalledWith("s1", 1);
      expect(client.sessionsCreate).toHaveBeenCalledWith("d", "i2", false);
      expect(client.sessionsLockRoi).toHaveBeenCalledWith(
        "s2",
        0,
        "part",
        [10, 20, 110, 90],
        "out",
      );
      expect(useViewStore.getState().snapshot?.protocol_session_id).toBe("s2");
      expect(useViewStore.getState().snapshot?.user_roi_full).toEqual([10, 20, 110, 90]);
      expect(screen.getByTestId("roi-reuse-status")).toHaveTextContent("已沿用上一張的框");
    });
  });

  it("does not lock a carried ROI when opening from the item list", async () => {
    useViewStore.setState({
      snapshot: snap({
        controls: { next: true },
        user_roi_full: [10, 20, 110, 90],
        class_id: "part",
      }),
      grantId: "g",
      datasetId: "d",
      items: [
        { item_id: "i1", image_id: "first", display_name: "first.png", class_id: "part" },
        { item_id: "i2", image_id: "second", display_name: "second.png", class_id: "part" },
      ],
      currentItemId: "i1",
      outputGrantId: "out",
      outputDisplayName: "output",
      uiError: null,
      reuseLastRoi: true,
    });
    const client = host(snap({ protocol_session_id: "s2", revision: 0, workflow_state: "IMAGE_OPEN", candidates: [] }));
    client.sessionsClose = vi.fn(async () => snap({ candidates: [] }));
    client.sessionsCreate = vi.fn(async () =>
      snap({ protocol_session_id: "s2", revision: 0, workflow_state: "IMAGE_OPEN", candidates: [] }),
    );
    render(<App host={client} />);

    await userEvent.click(screen.getByText("second.png"));

    await waitFor(() => expect(client.sessionsCreate).toHaveBeenCalledWith("d", "i2", false));
    expect(client.sessionsLockRoi).not.toHaveBeenCalled();
  });

  it("keeps the new IMAGE_OPEN session when carried lock_roi fails", async () => {
    useViewStore.setState({
      snapshot: snap({
        controls: { next: true },
        user_roi_full: [10, 20, 110, 90],
        class_id: "part",
      }),
      grantId: "g",
      datasetId: "d",
      items: [
        { item_id: "i1", image_id: "first", display_name: "first.png", class_id: "part" },
        { item_id: "i2", image_id: "second", display_name: "second.png", class_id: "part" },
      ],
      currentItemId: "i1",
      outputGrantId: "out",
      outputDisplayName: "output",
      uiError: null,
      reuseLastRoi: true,
    });
    const created = snap({
      protocol_session_id: "s2",
      revision: 0,
      workflow_state: "IMAGE_OPEN",
      candidates: [],
      user_roi_full: null,
    });
    const client = host(created);
    client.sessionsClose = vi.fn(async () => snap({ candidates: [] }));
    client.sessionsCreate = vi.fn(async () => created);
    client.sessionsLockRoi = vi.fn(async () => {
      throw new Error(JSON.stringify({ code: "validation_failed", message: "ROI is outside the image" }));
    });
    render(<App host={client} />);

    await userEvent.click(screen.getByTestId("next-image"));

    await waitFor(() => {
      expect(useViewStore.getState().snapshot?.protocol_session_id).toBe("s2");
      expect(useViewStore.getState().snapshot?.workflow_state).toBe("IMAGE_OPEN");
      expect(screen.getByTestId("operation-error")).toHaveTextContent("ROI is outside the image");
    });
    expect(client.sessionsLockRoi).toHaveBeenCalledTimes(1);
  });
});
