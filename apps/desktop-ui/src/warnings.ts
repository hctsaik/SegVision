export type UiWarning = { code: string; message: string };

const CHINESE_WARNING_MESSAGES: Record<string, string> = {
  TOUCHES_WORK_CROP_EDGE:
    "遮罩碰到工作區邊界，目標可能沒有完整框入。請按「擴大框選」，或確認結果後再儲存。",
  IMAGE_BOUNDARY_TRUNCATED: "目標碰到原始影像邊界，影像外的部分無法標註。",
};

export function warningMessageZh(warning: UiWarning): string {
  return CHINESE_WARNING_MESSAGES[warning.code] ?? `系統警告（${warning.code}）`;
}

export function uniqueWarnings(warnings: UiWarning[]): UiWarning[] {
  const seen = new Set<string>();
  return warnings.filter((warning) => {
    if (seen.has(warning.code)) return false;
    seen.add(warning.code);
    return true;
  });
}
