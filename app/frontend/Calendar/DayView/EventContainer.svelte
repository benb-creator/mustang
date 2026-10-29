<hbox class="event font-small"
  style="
    grid-row: {item.startRow + 1} / {item.endRow + 1};
    --lane: {item.lane};
    --lanes: {item.lanes};
    --color: {$event.color ?? $event.calendar?.color}"
  class:selected={$selectedEvent == event}>
  <slot />
</hbox>

<script lang="ts">
  import type { EventInTimeColumn } from "./DayColumn";
  import { selectedEvent } from "../selected";

  export let item: EventInTimeColumn;

  $: event = item.event;
</script>

<style>
  .event {
    grid-column: 1;
    position: relative;
    z-index: 1;
    width: calc(100% / var(--lanes));
    margin-inline-start: calc(100% * var(--lane) / var(--lanes));
    margin-block-end: 1px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
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
</style>
