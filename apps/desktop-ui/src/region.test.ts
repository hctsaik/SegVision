import { describe, expect, it } from "vitest";
import {
  backendLabel,
  candidateSourceLabel,
  computePhaseFromJob,
  regionBadge,
  regionStatus,
  workflowLabel,
} from "./region";

describe("region copy", () => {
  it("labels SAM box candidates as computed in the drawn region", () => {
    expect(candidateSourceLabel("sam_box")).toBe("來自黃框");
    expect(workflowLabel("PROPOSAL_READY")).toBe("請選遮罩");
    expect(workflowLabel("ACCEPTED")).toBe("已儲存");
    expect(backendLabel("fake")).toBe("假後端（非 MobileSAM）");
    expect(backendLabel("mobilesam")).toBe("MobileSAM CPU");
  });

  it("tells the operator to box a defect before SAM runs", () => {
    expect(
      regionStatus({
        hasImage: true,
        workflow: "IMAGE_OPEN",
        dinoOn: false,
        computePhase: "idle",
        hasRoi: false,
        candidateCount: 0,
      }),
    ).toMatch(/點兩個角建立黃框/);
  });

  it("says SAM is proposing inside the box while locking", () => {
    expect(
      regionStatus({
        hasImage: true,
        workflow: "IMAGE_OPEN",
        dinoOn: false,
        computePhase: "locking-sam",
        hasRoi: true,
        candidateCount: 0,
      }),
    ).toMatch(/黃框內/);
  });

  it("prefers a running sidecar propose job over a local wait flag", () => {
    expect(computePhaseFromJob("idle", { kind: "propose", status: "running" })).toBe("locking-sam");
    expect(computePhaseFromJob("matching-dino", { kind: "propose", status: "completed" })).toBe(
      "matching-dino",
    );
  });

  it("distinguishes a DINO-found region from a copied box", () => {
    expect(
      regionStatus({
        hasImage: true,
        workflow: "PROPOSAL_READY",
        dinoOn: true,
        computePhase: "idle",
        hasRoi: true,
        candidateCount: 1,
        prototype: { matched: true },
      }),
    ).toMatch(/已找到相似區域/);
    expect(regionBadge({ computePhase: "idle", dinoMatched: true, drafting: false })).toBe(
      "黃框＝搜尋範圍，不是切割結果",
    );
  });
});
