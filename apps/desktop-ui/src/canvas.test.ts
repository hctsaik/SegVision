import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnnotationCanvas, nearestTwoPointCorner, pointLabelForInput, rectFromCorners } from "./canvas";
import { BRUSH_RADII, useViewStore } from "./store";

describe("MobileSAM point input", () => {
  it("maps the explicit add tool to a foreground point", () => {
    expect(pointLabelForInput("point", 0)).toBe(1);
  });

  it("maps the explicit remove tool and right click to background points", () => {
    expect(pointLabelForInput("point-remove", 0)).toBe(0);
    expect(pointLabelForInput("point", 2)).toBe(0);
  });

  it("includes radius zero as a one-pixel pencil", () => {
    expect(BRUSH_RADII[0]).toBe(0);
    expect(BRUSH_RADII).toEqual([0, 1, 2]);
    expect(useViewStore.getState().brushRadius).toBe(0);
  });

  it("builds a half-open rectangle from two opposite corners", () => {
    expect(rectFromCorners({ x: 18, y: 14 }, { x: 4, y: 6 })).toEqual([4, 6, 19, 15]);
  });

  it("chooses the closer corner for every completed-box tap", () => {
    const first = { x: 10, y: 10 };
    const opposite = { x: 90, y: 90 };
    expect(nearestTwoPointCorner({ x: 14, y: 13 }, first, opposite)).toBe("first");
    expect(nearestTwoPointCorner({ x: 86, y: 88 }, first, opposite)).toBe("opposite");
    expect(nearestTwoPointCorner({ x: 50, y: 50 }, first, opposite)).toBe("first");
  });
});

describe("two-point brush work area input", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    useViewStore.setState({ snapshot: null, tool: "roi" });
  });

  it("commits a rectangle after two clicks without dragging", async () => {
    class TestImage extends EventTarget {
      naturalWidth = 32;
      naturalHeight = 24;
      complete = true;
      src = "";
    }
    vi.stubGlobal("Image", TestImage);
    useViewStore.setState({
      tool: "edit-region",
      snapshot: {
        protocol_session_id: "s1",
        workflow_state: "IMAGE_OPEN",
        revision: 0,
        candidates: [],
        warnings: [],
        job: { job_id: null, kind: null, status: null },
        assets: { source_image: null, thumbnail: null, mask: null },
        controls: { local_edit: true },
      },
    });
    const onRoi = vi.fn();
    const onStroke = vi.fn();
    render(
      createElement(AnnotationCanvas, {
        imageUrl: "asset://image",
        onRoi,
        onPoint: vi.fn(),
        onStroke,
      }),
    );
    const canvas = screen.getByTestId("annotation-canvas");
    await waitFor(() => expect(canvas).toHaveAttribute("data-image-width", "32"));
    act(() => useViewStore.getState().setViewport({ zoom: 1, panX: 0, panY: 0, dpr: 1 }));
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
      left: 0,
      top: 0,
      width: 32,
      height: 24,
      right: 32,
      bottom: 24,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    const pointer = (type: string, x: number, y: number) => {
      const event = new MouseEvent(type, { bubbles: true, clientX: x, clientY: y, button: 0 });
      Object.defineProperties(event, { pointerId: { value: 7 } });
      fireEvent(canvas, event);
    };
    await act(async () => {
      pointer("pointerdown", 4, 5);
      pointer("pointerup", 4, 5);
    });
    await waitFor(() => expect(screen.getByTestId("two-point-corner-1")).toBeInTheDocument());
    expect(screen.getByTestId("two-point-box-instruction")).toHaveTextContent("第一個角已選");
    await act(async () => {
      pointer("pointermove", 18, 15);
    });
    expect(screen.queryByTestId("two-point-corner-2")).not.toBeInTheDocument();
    await act(async () => {
      pointer("pointerdown", 18, 15);
      pointer("pointerup", 18, 15);
    });

    expect(onRoi).not.toHaveBeenCalled();
    expect(onStroke).not.toHaveBeenCalled();
    expect(screen.getByTestId("edit-region-overlay")).toBeInTheDocument();
    expect(screen.getByTestId("two-point-corner-2")).toBeInTheDocument();
    expect(screen.getByTestId("two-point-box-instruction")).toHaveTextContent("編輯範圍已建立");

    await act(async () => {
      pointer("pointerdown", 5, 6);
      pointer("pointerup", 5, 6);
    });
    expect(screen.getByTestId("two-point-corner-1")).toHaveAttribute("data-image-x", "5");
    expect(screen.getByTestId("two-point-corner-1")).toHaveAttribute("data-image-y", "6");
    await act(async () => {
      pointer("pointerdown", 17, 14);
      pointer("pointerup", 17, 14);
    });
    expect(screen.getByTestId("two-point-corner-2")).toHaveAttribute("data-image-x", "17");
    expect(screen.getByTestId("two-point-corner-2")).toHaveAttribute("data-image-y", "14");
    await act(async () => {
      // PhoneCV has no corner hit radius: a completed-box tap anywhere on the
      // canvas replaces whichever corner is closer.
      pointer("pointerdown", 31, 0);
      pointer("pointerup", 31, 0);
    });
    expect(screen.getByTestId("two-point-corner-2")).toHaveAttribute("data-image-x", "31");
    expect(screen.getByTestId("two-point-corner-2")).toHaveAttribute("data-image-y", "0");

    act(() => useViewStore.getState().setTool("brush"));
    await act(async () => {
      pointer("pointerdown", 4, 5);
      pointer("pointerup", 4, 5);
    });
    expect(onStroke).toHaveBeenCalledWith([[4, 5]], false, [5, 0, 32, 7]);
  });
});

describe("two-point SAM ROI input", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    useViewStore.setState({ snapshot: null, tool: "roi" });
  });

  it("uses two taps for SAM ROI instead of a drag", async () => {
    class TestImage extends EventTarget {
      naturalWidth = 32;
      naturalHeight = 24;
      complete = true;
      src = "";
    }
    vi.stubGlobal("Image", TestImage);
    useViewStore.setState({
      tool: "roi",
      snapshot: {
        protocol_session_id: "s1",
        workflow_state: "IMAGE_OPEN",
        revision: 0,
        candidates: [],
        warnings: [],
        job: { job_id: null, kind: null, status: null },
        assets: { source_image: null, thumbnail: null, mask: null },
        controls: { roi: true },
      },
    });
    const onRoi = vi.fn();
    render(
      createElement(AnnotationCanvas, {
        imageUrl: "asset://image",
        onRoi,
        onPoint: vi.fn(),
        onStroke: vi.fn(),
      }),
    );
    const canvas = screen.getByTestId("annotation-canvas");
    await waitFor(() => expect(canvas).toHaveAttribute("data-image-width", "32"));
    act(() => useViewStore.getState().setViewport({ zoom: 1, panX: 0, panY: 0, dpr: 1 }));
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
      left: 0,
      top: 0,
      width: 32,
      height: 24,
      right: 32,
      bottom: 24,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    const pointer = (type: string, x: number, y: number) => {
      const event = new MouseEvent(type, { bubbles: true, clientX: x, clientY: y, button: 0 });
      Object.defineProperties(event, { pointerId: { value: 7 } });
      fireEvent(canvas, event);
    };

    await act(async () => {
      pointer("pointerdown", 4, 5);
      pointer("pointerup", 4, 5);
      pointer("pointermove", 18, 15);
    });
    expect(onRoi).not.toHaveBeenCalled();
    expect(screen.getByTestId("two-point-corner-1")).toBeInTheDocument();
    expect(screen.queryByTestId("two-point-corner-2")).not.toBeInTheDocument();

    await act(async () => {
      pointer("pointerdown", 18, 15);
      pointer("pointerup", 18, 15);
    });
    expect(onRoi).toHaveBeenCalledWith([4, 5, 19, 16]);
    expect(screen.queryByTestId("two-point-corner-1")).not.toBeInTheDocument();
    expect(screen.queryByTestId("two-point-corner-2")).not.toBeInTheDocument();
  });
});

describe("local brush input", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    useViewStore.setState({ snapshot: null, tool: "roi" });
  });

  it("commits a captured brush stroke when the pointer is released", async () => {
    class TestImage extends EventTarget {
      naturalWidth = 32;
      naturalHeight = 24;
      complete = true;
      src = "";
    }
    vi.stubGlobal("Image", TestImage);
    useViewStore.setState({
      tool: "brush",
      snapshot: {
        protocol_session_id: "s1",
        workflow_state: "LOCAL_EDITING",
        revision: 4,
        selected_candidate_id: "c1",
        candidates: [
          {
            candidate_id: "c1",
            source: "manual_edit",
            capabilities: { can_refine: false, can_local_edit: true, can_commit: true },
            mask_token: "m1",
          },
        ],
        warnings: [],
        job: { job_id: null, kind: null, status: null },
        assets: { source_image: null, thumbnail: null, mask: null },
        controls: { local_edit: true },
      },
    });
    const onStroke = vi.fn();
    render(
      createElement(AnnotationCanvas, {
        imageUrl: "asset://image",
        onRoi: vi.fn(),
        onPoint: vi.fn(),
        onStroke,
      }),
    );
    const canvas = screen.getByTestId("annotation-canvas");
    await waitFor(() => expect(canvas).toHaveAttribute("data-image-width", "32"));
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
      left: 0,
      top: 0,
      width: 32,
      height: 24,
      right: 32,
      bottom: 24,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    const pointer = (type: string, x: number, y: number) => {
      const event = new MouseEvent(type, { bubbles: true, clientX: x, clientY: y, button: 0 });
      Object.defineProperties(event, {
        pointerId: { value: 7 },
      });
      fireEvent(canvas, event);
    };
    pointer("pointerdown", 4, 5);
    pointer("pointermove", 8, 9);
    pointer("pointerup", 8, 9);

    expect(onStroke).toHaveBeenCalledTimes(1);
    expect(onStroke.mock.calls[0]?.[0]).toEqual(expect.arrayContaining([expect.any(Array)]));
    expect(onStroke.mock.calls[0]?.[1]).toBe(false);
  });
});
