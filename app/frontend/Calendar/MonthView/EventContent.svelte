<Clickable onClick={onSelect} onDoubleClick={onOpen}>
  <hbox class="event font-small"
    class:unanswered={$event.isUnanswered}
    class:cancelled={$event.isCancelled}
    title={eventAsText}>
    {#if showTime}
      <hbox class="time">
        {startTime}
      </hbox>
    {/if}
    <hbox class="title">{$event.title}</hbox>
  </hbox>
</Clickable>

<script lang="ts">
  import type { Event } from "../../../logic/Calendar/Event";
  import { openEvent } from "../open";
  import { selectedEvent } from "../selected";
  import Clickable from "../../Shared/Clickable.svelte";
  import { getDurationString } from "../../../logic/util/date";
  import { getDateTimeLocale } from "../../../l10n/l10n";

  export let event: Event;
  export let showTime = true;

  $: startTime = $event.startTime.toLocaleString(getDateTimeLocale(), {
    hour: "numeric",
    minute: $event.startTime.getMinutes() != 0 ? "2-digit" : undefined,
  });
  $: eventAsText = ($event.allDay ? "" : `${startTime} – ${getDurationString(event.endTime.getTime() - event.startTime.getTime())}\n`) +
     event.title +
     (event.participants.isEmpty ? "" : "\n" + event.participants.getIndexRange(0, 4).map(person => person.name).join(", "));

  function onSelect() {
    $selectedEvent = event;
  }

  function onOpen() {
    openEvent(event, true);
  }
</script>

<style>
  .event {
    background-color: var(--color);
    color: lch(from var(--color) calc((49.44 - l) * infinity) 0 0);
    padding-inline-start: 4px;
    margin-inline-end: 3px;
    border-radius: 3px;
    width: 100%;
    height: 100%;
    min-width: 0;
    overflow: hidden;
    --stripe-color: rgb(from var(--color) r g b / 50%);
  }
  @media (prefers-color-scheme: dark) {
    .event {
      background-image:
        linear-gradient(var(--color), var(--color)),
        linear-gradient(#000000AA, #000000AA);
      background-blend-mode: overlay;
      background-color: unset;
      color: unset;
      --stripe-color: rgb(from var(--color) r g b / 25%);
    }
  }
  /* <copied from="../DayView/EventContent.svelte"> */
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
  .cancelled .time,
  .cancelled .title {
    text-decoration: line-through;
  }
  /* </copied> */
  .event:hover {
    background-color: #20AF9E70;
  }
  .time {
    margin-inline-end: 4px;
    font-weight: 600;
  }
  .title {
    display: block;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  /* <copied from="../DayView/AllDayEvent.svelte"> Fresh event look */
  :global(.fresh) .event {
    box-sizing: border-box;
    align-items: center;
    padding-inline: 4px;
    margin-inline-end: 2px;
    border-inline-start: 3px solid var(--color);
    border-radius: var(--radius-s);
    background-color: color-mix(in srgb, var(--color) var(--tint-strength), var(--l3-bg));
    background-image: none;
    background-blend-mode: normal;
    color: var(--fg-1);
    font-size: var(--text-s);
  }
  :global(.fresh) .event:hover {
    background-color: color-mix(in srgb, var(--color) calc(var(--tint-strength) + 6%), var(--l3-bg));
  }
  :global(.fresh) .event.unanswered {
    background-image: repeating-linear-gradient(135deg, transparent 0 6px, color-mix(in srgb, var(--color) 18%, transparent) 6px 8px);
  }
  :global(.fresh) .event.cancelled {
    background-image: none;
    opacity: 60%;
  }
  :global(.fresh) .event.cancelled.unanswered {
    opacity: 40%;
  }
  /* </copied> */
  :global(.fresh) .time {
    font-weight: 400;
    color: var(--fg-2);
    font-variant-numeric: tabular-nums;
  }
  :global(.fresh) .title {
    font-weight: 600;
  }
</style>
