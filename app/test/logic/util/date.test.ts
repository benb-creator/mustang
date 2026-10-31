// @vitest-environment happy-dom
import { getDateString, getDateTimeString, getDayStart, getFormattedDateString, getTimeString, getTimeStringWithoutAMPM, getWeekStart } from "../../../logic/util/date";
import { saveDateTimeLocale } from "../../../l10n/l10n";
import { afterEach, expect, test } from "vitest";

const time = new Date(2026, 9, 29, 15, 5);

afterEach(() => {
  saveDateTimeLocale("");
});

test("Time without AM/PM leaves out only the AM/PM part", () => {
  for (let locale of ["en-US", "es-US", "ko-KR"]) {
    saveDateTimeLocale(locale);
    let ampm = new Intl.DateTimeFormat(locale, { hour: "numeric", hour12: true })
      .formatToParts(time)
      .find(part => part.type == "dayPeriod")
      .value;
    let withoutAMPM = getTimeStringWithoutAMPM(time);
    expect(getTimeString(time)).toContain(ampm);
    expect(withoutAMPM).not.toContain(ampm);
    expect(getTimeString(time)).toContain(withoutAMPM);
    expect(withoutAMPM).toContain("05");
    expect(withoutAMPM).toBe(withoutAMPM.trim());
  }
});

test("Time without AM/PM is the normal time in 24-hour locales", () => {
  for (let locale of ["de-DE", "en-GB"]) {
    saveDateTimeLocale(locale);
    expect(getTimeStringWithoutAMPM(time)).toBe(getTimeString(time));
  }
});

test("Day start is midnight of the same day, and the week starts on Monday", () => {
  let dayStart = getDayStart(time);
  expect(dayStart).toEqual(new Date(2026, 9, 29));
  expect(time.getTime()).toBe(new Date(2026, 9, 29, 15, 5).getTime());
  // Sunday belongs to the week before
  expect(getWeekStart(new Date(2026, 10, 1, 12, 0))).toEqual(new Date(2026, 9, 26));
});

test("Formatted dates are the same as with toLocaleString(), also after the locale changed", () => {
  let dates = [time, new Date(2026, 2, 29, 3, 30), new Date(2026, 9, 25, 2, 30), new Date(1999, 11, 31, 23, 59), new Date()];
  let optionSets: Intl.DateTimeFormatOptions[] = [
    { hour: "numeric", minute: "numeric" },
    { weekday: "short", hour: "numeric", minute: "numeric" },
    { month: "2-digit", day: "2-digit", hour: "numeric", minute: "numeric" },
    { year: "numeric", month: "2-digit", day: "2-digit", hour: "numeric", minute: "numeric" },
    { weekday: "long" },
    { weekday: "long", day: "numeric", month: "long", year: "numeric" },
  ];
  for (let round = 0; round < 2; round++) {
    for (let locale of ["en-US", "de-DE", "ja-JP", "ar-EG", "fr-CA"]) {
      saveDateTimeLocale(locale);
      for (let date of dates) {
        for (let options of optionSets) {
          expect(getFormattedDateString(date, options)).toBe(date.toLocaleString(locale, options));
        }
      }
    }
  }
});

test("A message from today shows the time in the locale", () => {
  for (let locale of ["en-US", "de-DE", "ko-KR"]) {
    saveDateTimeLocale(locale);
    let now = new Date();
    expect(getTimeString(now)).toBe(now.toLocaleString(locale, { hour: "numeric", minute: "numeric" }));
    expect(getDateTimeString(now)).toBe(getTimeString(now));
  }
});

test("An invalid date is shown as with toLocaleString()", () => {
  let invalid = new Date("not a date");
  expect(getDateTimeString(invalid)).toBe(invalid.toLocaleString());
  expect(getDateString(invalid)).toBe(invalid.toLocaleString());
  expect(getTimeString(invalid)).toBe(invalid.toLocaleString());
});
