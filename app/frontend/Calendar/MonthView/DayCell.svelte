<Clickable onClick={selectDay} {onDoubleClick}>
  <vbox class="day-cell"
    style="grid-column: {column}"
    class:selected={start.getTime() == $selectedDate?.getTime()}>
    {#if withMonthOnFirst && start.getDate() == 1 ||
      withMonthOnMonday && start.getDay() == 1 }
      <hbox class="month-name font-normal">
        {start.toLocaleDateString(getDateTimeLocale(), { month: "long" })}
      </hbox>
    {/if}
    <vbox class="current-time-marker-range">
      <CurrentTimeMarker day={start} startHour={WeekRowLayout.kStartHour} endHour={WeekRowLayout.kEndHour} />
    </vbox>
  </vbox>
</Clickable>

<script lang="ts">
  import { selectedDate } from "../selected";
  import Clickable from "../../Shared/Clickable.svelte";
  import CurrentTimeMarker from "../CurrentTimeMarker.svelte";
  import { WeekRowLayout } from "./WeekRow";
  import { k1HourMS } from "../../Util/date";
  import { getDateTimeLocale } from "../../../l10n/l10n";
  import { createEventDispatcher } from "svelte";
  const dispatchEvent = createEventDispatcher<{ celldblclick: { start: Date, mouseEvent: MouseEvent } }>();

  export let start: Date;
  export let column: number;
  export let withMonthOnFirst = false;
  export let withMonthOnMonday = false;

  function selectDay() {
    $selectedDate = start;
  }

  function onDoubleClick(mouseEvent: MouseEvent) {
    let startTime = new Date(start.getTime() + 10 * k1HourMS);
    dispatchEvent("celldblclick", { start: startTime, mouseEvent });
  }
</script>

<style>
  .day-cell {
    grid-row: 1 / -1;
    position: relative;
    border-left: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
  }
  .day-cell.selected {
    box-shadow: inset 0 0 0 2px var(--selected-bg);
  }
  .day-cell:hover {
    background-color: var(--hover-bg);
    background-image: linear-gradient(
      color-mix(in srgb, var(--selected-calendar-color) 10%, transparent),
      color-mix(in srgb, var(--selected-calendar-color) 10%, transparent));
    color: var(--hover-fg);
  }
  .current-time-marker-range {
    position: absolute;
    top: 0px;
    inset-inline: 0px;
    height: calc(var(--rows) * var(--row-height));
  }
  .month-name {
    position: absolute;
    bottom: 0px;
    left: 0px;
    overflow: hidden;
    z-index: -1;

    width: 100%;
    aspect-ratio: 1/1;
    margin-block-end: 8px;
    transform: rotate(270deg);

    color: #8B8B8B;
    opacity: 50%;
    letter-spacing: 0.378px;
    text-transform: uppercase;
    font-weight: 300;
  }
  @container (max-height: 400px)  {
    .month-name {
      display: none;
    }
  }
</style>
