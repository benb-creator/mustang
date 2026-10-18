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
  import { getToday } from "../../Util/date";
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
    align-items: center;
    padding: 4px 6px;
    border-inline-start: 1px solid var(--border);
    font-variant-numeric: tabular-nums;
  }
  .date-number {
    min-width: 24px;
    height: 24px;
    box-sizing: border-box;
    align-items: center;
    justify-content: center;
    padding-inline: 4px;
  }
  @container (max-height: 400px) {
    .day {
      padding: 2px 6px 0px 6px;
    }
  }
  .today .date-number {
    background-color: var(--accent);
    color: var(--accent-fg);
    border-radius: 12px;
    font-weight: 700;
  }
  .month {
    font-size: 90%;
    margin-inline-start: 4px;
    color: var(--fg-muted);
  }
  .today-icon {
    display: none;
  }
  .day.today .today-icon {
    display: flex;
    margin-inline-start: 6px;
    justify-content: start;
    align-items: center;
    color: var(--accent-text);
  }
  .today-icon :global(svg) {
    stroke-width: 1px;
  }
</style>
