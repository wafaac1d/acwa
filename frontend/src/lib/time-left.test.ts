import { describe, expect, it } from "vitest";
import { timeLeftLabel } from "./time-left";

const now = Date.parse("2026-11-06T12:00:00Z");

describe("timeLeftLabel", () => {
  it("counts days, hours and minutes until the slot", () => {
    expect(timeLeftLabel("2026-11-08T15:20:00Z", now)).toBe("осталось 2 д 3 ч");
    expect(timeLeftLabel("2026-11-06T14:10:00Z", now)).toBe("осталось 2 ч 10 мин");
    expect(timeLeftLabel("2026-11-06T12:25:00Z", now)).toBe("осталось 25 мин");
    expect(timeLeftLabel("2026-11-06T12:00:30Z", now)).toBe("осталось меньше минуты");
  });

  it("says when the slot time has already passed", () => {
    expect(timeLeftLabel("2026-11-06T11:00:00Z", now)).toBe("время уже наступило");
  });
});
