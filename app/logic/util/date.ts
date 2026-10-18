import { getDateTimeLocale } from "../../l10n/l10n";

// <copied from="../../frontend/Util/date.ts">
/**
 * @param weekday day of the week
 * @param form How long the name should be
 *    narrow = 1 char
 *    short = 2 chars
 *    long = full name
 * @return Name for the weekday, e.g. "Mo" or "Monday" */
export function weekdayLabel(weekday: number, form: "long" | "short" | "narrow") {
  let date = new Date(2010, 2, weekday);
  return date.toLocaleDateString(getDateTimeLocale(), { weekday: form });
};

/** Monday to Sunday, in order (sorted).
 *
 * If we ever want to support Sunday being the first day of the week,
 * simply change this to `[0, 1, 2, 3, 4, 5, 6]` at runtime. */
export const kAllWeekdays = [1, 2, 3, 4, 5, 6, 0];
// </copied>

// <copied from="../../frontend/Util/date.ts">
export function myTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}
// </copied>

// <copied from="../../frontend/Util/date.ts">
/** 1 day, in seconds */
export const k1MinuteS = 60;
export const k1HourS = 3600;
export const k1DayS = 86400;
export const k1WeekS = 7 * k1DayS;
export const k1MonthS = 31 * k1DayS;
/** 1 day, in milliseconds */
export const k1MinuteMS = k1MinuteS * 1000;
export const k1HourMS = k1HourS * 1000;
export const k1DayMS = k1DayS * 1000;
export const k1WeekMS = k1WeekS * 1000;
export const k1MonthMS = k1MonthS * 1000;
// </copied>
