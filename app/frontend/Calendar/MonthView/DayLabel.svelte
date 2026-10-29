<Clickable onClick={selectDay} onDoubleClick={changeToDay}>
  <hbox class="day font-small"
    style="grid-column: {column}"
    class:today={day.getTime() == today.getTime()}>
    <hbox class="date-number">
      {day.toLocaleDateString(getDateTimeLocale(), { day: "numeric" })}
    </hbox>
    {#if withMonthOnFirst && day.getDate() == 1 ||
            withMonthOnMonday && day.getDay() == 1 }
      <hbox class="month">
        {day.toLocaleDateString(getDateTimeLocale(), { month: "short" })}
      </hbox>
    {/if}
    <hbox class="today-icon" flex>
      <TodayIcon size={14} />
    </hbox>
  </hbox>
</Clickable>

<script lang="ts">
  import { selectedDate } from "../selected";
  import { getToday } from "../../../logic/util/date";
  import Clickable from "../../Shared/Clickable.svelte";
  import TodayIcon from "lucide-svelte/icons/home";
  import { getDateTimeLocale } from "../../../l10n/l10n";
  import { getLocalStorage } from "../../Util/LocalStorage";

  export let day: Date
  export let column: number;
  export let withMonthOnMonday = true;
  export let withMonthOnFirst = true;

  let today = getToday();
  // Update today at midnight
  $: setTimeout(() => today = getToday(), new Date(today).setDate(today.getDate() + 1) - Date.now());

  function selectDay() {
    $selectedDate = day;
  }

  function changeToDay() {
    $selectedDate = day;
    getLocalStorage("calendar.view").value = 2;
  }
</script>

<style>
  .day {
    grid-row: 1;
    padding: 4px 8px;
    border-left: 1px dotted var(--border);
    background-color: var(--bg);
  }
  @container (max-height: 400px) {
    .day {
      padding: 2px 6px 0px 6px;
    }
  }
  .today {
    padding: 0px 8px;
  }
  .today .date-number {
    background-color: black;
    color: white;
    border-radius: 1000px;
    padding: 4px 6px;
  }
  @media (prefers-color-scheme: dark) {
    .today .date-number {
      background-color: var(--selected-bg);
    }
  }
  .month {
    font-size: 90%;
    align-self: end;
    margin-inline-start: 8px;
  }
  .today-icon {
    display: none;
  }
  .day.today .today-icon {
    display: flex;
    margin-inline-start: 8px;
    justify-content: start;
    align-items: center;
  }
  .today-icon :global(svg) {
    stroke-width: 1px;
  }
  :global(.fresh) .day {
    align-items: center;
    min-height: 26px;
    box-sizing: border-box;
    padding: 2px 6px;
    border-left: 1px solid var(--border-subtle);
    background-color: transparent;
    color: var(--fg-1);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  :global(.fresh) .date-number {
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
    min-width: 22px;
    height: 22px;
    padding: 0 5px;
    border-radius: 11px;
  }
  :global(.fresh) .today .date-number {
    padding: 0 5px;
    background-color: var(--signal);
    color: var(--fg-on-signal);
  }
  :global(.fresh) .month {
    align-self: center;
    margin-inline-start: 4px;
    font-weight: 400;
    color: var(--fg-2);
  }
  :global(.fresh) .day.today .today-icon {
    display: none;
  }
</style>
