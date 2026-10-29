<hbox class="day">
  {startDay}
</hbox>
<hbox class="time">
  {#if !$event.allDay}
    {startTime}
  {/if}
</hbox>
<hbox class="event title"
  on:click
  on:click={onSelect}
  on:dblclick={onOpen}
  title={eventAsText}
  style="--color: {event.color ?? event.calendar?.color}"
  class:all-day={$event.allDay}
  class:selected={$selectedEvent == event}
  class:unanswered={$event.isUnanswered}
  class:cancelled={$event.isCancelled}
  >
  {$event.title}
</hbox>

<script lang="ts">
  import type { Event } from "../../../logic/Calendar/Event";
  import { selectedEvent } from "../selected";
  import { openEvent } from "../open";
  import { getDurationString } from "../../../logic/util/date";
  import { getDateTimeLocale } from "../../../l10n/l10n";

  export let event: Event;

  $: startDay = event.startTime.toLocaleString(getDateTimeLocale(), { day: "2-digit", month: "short" });
  $: startTime = event.startTime.toLocaleString(getDateTimeLocale(), { hour: "2-digit", minute: "2-digit" });
  $: eventAsText = (event.allDay ? "" : `${startTime} – ${getDurationString(event.endTime.getTime() - event.startTime.getTime())}\n`) +
     event.title +
     (event.participants.isEmpty ? "" : "\n" + event.participants.getIndexRange(0, 4).map(person => person.name).join(", "));

  function onSelect() {
    $selectedEvent = event;
  }

  function onOpen() {
    openEvent(event);
  }
</script>

<style>
  .event {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;

    background-color: var(--color);
    --stripe-color: rgb(from var(--color) r g b / 50%);
  }
  @media (prefers-color-scheme: dark) {
    .event {
      background-image:
        linear-gradient(var(--color), var(--color)),
        linear-gradient(#000000AA, #000000AA);
      background-blend-mode: overlay;
      background-color: unset;
      --stripe-color: rgb(from var(--color) r g b / 25%);
    }
  }
  /* <copied from="../DayView/EventContent.svelte"> */
  .event.unanswered {
    background-image: repeating-linear-gradient(-45deg, transparent 0 4px, var(--stripe-color) 4px 8px);
    background-blend-mode: normal;
    background-color: transparent;
  }
  .event.cancelled {
    --cancelled-stripe-color: rgb(from var(--stripe-color) r g b / calc(alpha / 6));
    background-image:
      repeating-linear-gradient(45deg, transparent 0 6px, var(--cancelled-stripe-color) 6px 10px),
      repeating-linear-gradient(-45deg, transparent 0 6px, var(--cancelled-stripe-color) 6px 10px);
    background-blend-mode: normal;
    background-color: transparent;
    text-decoration: line-through;
  }
  .event.cancelled.unanswered {
    opacity: 10%;
  }
  /* </copied> */
  .event:hover {
    background-color: #20AF9E70;
  }
  .event.all-day {
    opacity: 85%;
  }
  .time {
    font-weight: 600;
  }
  :global(.fresh) .day,
  :global(.fresh) .time {
    align-items: center;
    min-height: var(--list-row-height);
    padding-inline-start: 8px;
    font-size: var(--text-s);
    font-weight: 400;
    color: var(--fg-2);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  :global(.fresh) .event {
    align-items: center;
    display: flex;
    min-height: var(--list-row-height);
    padding-inline: 12px 8px;
    background-color: transparent;
    background-image: linear-gradient(var(--color), var(--color));
    background-repeat: no-repeat;
    background-position: left 0 center;
    background-size: 3px calc(100% - 8px);
    background-blend-mode: normal;
    color: var(--fg-1);
    opacity: 1;
  }
  :global([dir="rtl"].fresh) .event {
    background-position: right 0 center;
  }
  :global(.fresh) .event:hover {
    background-color: transparent;
  }
  :global(.fresh) .event.unanswered {
    background-image:
      linear-gradient(var(--color), var(--color)),
      repeating-linear-gradient(135deg, transparent 0 6px, color-mix(in srgb, var(--color) 18%, transparent) 6px 8px);
    background-size: 3px calc(100% - 8px), 100% 100%;
  }
  :global(.fresh) .event.cancelled {
    background-image: linear-gradient(var(--color), var(--color));
    background-size: 3px calc(100% - 8px);
    opacity: 60%;
  }
</style>
