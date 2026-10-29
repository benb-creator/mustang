<vbox class="day-header" class:today={isToday}>
  <hbox class="weekday">{day.toLocaleDateString(getDateTimeLocale(), { weekday: "short" })}</hbox>
  <hbox class="date">{day.toLocaleDateString(getDateTimeLocale(), { day: "numeric" })}</hbox>
</vbox>

<script lang="ts">
  import { getToday } from "../../../logic/util/date";
  import { getDateTimeLocale } from "../../../l10n/l10n";

  export let day: Date;

  $: isToday = day.getTime() == getToday().getTime();
</script>

<style>
  .day-header {
    align-items: start;
    gap: 2px;
    padding: 6px 8px 8px 8px;
    min-width: 0;
    overflow: hidden;
  }
  .weekday {
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-weight: 600;
    color: var(--fg-2);
    white-space: nowrap;
  }
  .date {
    align-items: center;
    justify-content: center;
    min-width: 28px;
    height: 28px;
    margin-inline-start: -4px;
    padding-inline: 4px;
    box-sizing: border-box;
    border-radius: 14px;
    font-size: 18px;
    line-height: 22px;
    font-weight: 600;
    color: var(--fg-1);
    font-variant-numeric: tabular-nums;
  }
  .today .weekday {
    color: var(--fg-1);
  }
  .today .date {
    background-color: var(--signal);
    color: var(--fg-on-signal);
  }
</style>
