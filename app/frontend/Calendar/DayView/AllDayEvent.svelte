<Clickable onClick={onSelect} onDoubleClick={onOpen}>
  <hbox class="event font-small"
    title={eventAsText}
    style="grid-column: {item.startDay + 1} / {item.endDay + 1}; grid-row: {item.lane + 1}; --account-color: {event.calendar?.color}"
    class:selected={$selectedEvent == event}
    class:unanswered={$event.isUnanswered}
    class:cancelled={$event.isCancelled}>
    <hbox class="title">{event.title}</hbox>
  </hbox>
</Clickable>

<script lang="ts">
  import type { EventInDayRow } from "../MonthView/WeekRow";
  import Clickable from "../../Shared/Clickable.svelte";
  import { openEvent } from "../open";
  import { selectedEvent } from "../selected";

  export let item: EventInDayRow;

  $: event = item.event;
  $: eventAsText = event.title;

  function onSelect() {
    $selectedEvent = event;
  }

  function onOpen() {
    openEvent(event, true);
  }
</script>

<style>
  .event {
    position: relative;
    padding-block: 4px;
    padding-inline: 6px;
    margin-block-end: 2px;
    margin-inline-start: 1px;
    margin-inline-end: 3px;
    border-radius: 3px;
    border-inline-start: 3px solid color-mix(in srgb, var(--account-color) 60%, black);
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;

    background-color: var(--account-color);
    color: lch(from var(--account-color) calc((49.44 - l) * infinity) 0 0);
    --stripe-color: rgb(from var(--account-color) r g b / 50%);
  }
  @media (prefers-color-scheme: dark) {
    .event {
      background-color: color-mix(in srgb, var(--account-color) 40%, var(--bg));
      border-inline-start-color: var(--account-color);
      color: var(--fg);
      --stripe-color: rgb(from var(--account-color) r g b / 25%);
    }
  }
  /* <copied from="EventContent.svelte"> */
  .event.unanswered {
    background-image: repeating-linear-gradient(-45deg, transparent 0 4px, var(--stripe-color) 4px 8px);
    background-blend-mode: normal;
    background-color: transparent;
    color: unset;
  }
  .event.cancelled {
    --cancelled-stripe-color: rgb(from var(--stripe-color) r g b / calc(alpha / 6));
    background-image:
      repeating-linear-gradient(45deg, transparent 0 6px, var(--cancelled-stripe-color) 6px 10px),
      repeating-linear-gradient(-45deg, transparent 0 6px, var(--cancelled-stripe-color) 6px 10px);
    background-blend-mode: normal;
    background-color: transparent;
    color: unset;
  }
  .event.cancelled.unanswered {
    opacity: 10%;
  }
  .cancelled .title {
    text-decoration: line-through;
  }
  /* </copied> */
  .event:hover {
    filter: brightness(0.94);
  }
  @media (prefers-color-scheme: dark) {
    .event:hover {
      filter: brightness(1.25);
    }
  }
  .event.selected {
    outline: 2px solid var(--fg);
    outline-offset: -2px;
  }
</style>
