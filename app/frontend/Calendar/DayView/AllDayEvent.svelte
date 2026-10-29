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
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    opacity: 85%;

    background-color: var(--account-color);
    color: lch(from var(--account-color) calc((49.44 - l) * infinity) 0 0);
    --stripe-color: rgb(from var(--account-color) r g b / 50%);
  }
  @media (prefers-color-scheme: dark) {
    .event {
      background-image:
        linear-gradient(var(--account-color), var(--account-color)),
        linear-gradient(#000000BB, #000000BB);
      background-blend-mode: overlay;
      background-color: unset;
      color: unset;
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
    background-color: #20AF9E70;
  }
  /* <copied to="EventContent.svelte, ../MonthView/EventContent.svelte"> Fresh event look */
  :global(.fresh) .event {
    box-sizing: border-box;
    height: 22px;
    align-items: center;
    padding-block: 0;
    padding-inline: 6px;
    margin-block-end: 2px;
    margin-inline: 1px 3px;
    border-inline-start: 3px solid var(--account-color);
    border-radius: var(--radius-s);
    opacity: 1;
    background-color: color-mix(in srgb, var(--account-color) var(--tint-strength), var(--l3-bg));
    background-image: none;
    background-blend-mode: normal;
    color: var(--fg-1);
    font-size: var(--text-s);
    font-weight: 600;
  }
  :global(.fresh) .event:hover {
    background-color: color-mix(in srgb, var(--account-color) calc(var(--tint-strength) + 6%), var(--l3-bg));
  }
  :global(.fresh) .event.unanswered {
    background-image: repeating-linear-gradient(135deg, transparent 0 6px, color-mix(in srgb, var(--account-color) 18%, transparent) 6px 8px);
  }
  :global(.fresh) .event.cancelled {
    background-image: none;
    opacity: 60%;
  }
  :global(.fresh) .event.cancelled.unanswered {
    opacity: 40%;
  }
  /* </copied> */
  :global(.fresh) .event.selected {
    outline: 2px solid color-mix(in srgb, var(--account-color) 70%, var(--fg-1));
    outline-offset: -2px;
    box-shadow: var(--shadow-pop);
  }
  :global(.fresh) .title {
    display: block;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
