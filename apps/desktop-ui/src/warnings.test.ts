import { describe, expect, it } from "vitest";
import { uniqueWarnings, warningMessageZh } from "./warnings";

describe("warning presentation", () => {
  const edgeWarning = {
    code: "TOUCHES_WORK_CROP_EDGE",
    message: "foreground touches the padded work-crop boundary",
  };

  it("translates the work-crop warning into actionable Chinese", () => {
    expect(warningMessageZh(edgeWarning)).toContain("遮罩碰到工作區邊界");
    expect(warningMessageZh(edgeWarning)).toContain("擴大框選");
    expect(warningMessageZh(edgeWarning)).not.toContain("foreground");
  });

  it("shows the same warning code only once", () => {
    expect(uniqueWarnings([edgeWarning, edgeWarning, edgeWarning])).toEqual([edgeWarning]);
  });
});
