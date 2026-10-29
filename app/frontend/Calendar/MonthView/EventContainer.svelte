<hbox class="event font-small"
  style="grid-column: {item.startDay + 1} / {item.endDay + 1}; grid-row: {item.startRow + 1} / {item.endRow + 1}; --lane: {item.lane}; --lanes: {item.lanes}; --color: {$event.color ?? $event.calendar?.color}"
  class:all-day={$event.allDay}
  class:selected={$selectedEvent == event}>
  <EventContent {event} showTime={!$event.allDay && !item.continuesBefore} />
</hbox>

<script lang="ts">
  import type { EventInWeekRow } from "./WeekRow";
  import { selectedEvent } from "../selected";
  import EventContent from "./EventContent.svelte";

  export let item: EventInWeekRow;

  $: event = item.event;
</script>

<style>
  .event {
    position: relative;
    width: calc(100% / var(--lanes) - 1px);
    margin-block-end: 1px;
    margin-inline-start: calc(100% * var(--lane) / var(--lanes) + 1px);
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  .event.all-day {
    opacity: 85%;
  }
  :global(.fresh) .event.all-day {
    opacity: 1;
  }
  :global(.fresh) .event.selected {
    z-index: 2;
    overflow: visible;
  }
  :global(.fresh) .event.selected :global(.event) {
    outline: 2px solid color-mix(in srgb, var(--color) 70%, var(--fg-1));
    outline-offset: -2px;
    box-shadow: var(--shadow-pop);
  }
  :global(.fresh) .event:not(.all-day) :global(.event:not(:hover)) {
    background-color: transparent;
  }
</style>
