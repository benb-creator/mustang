<vbox class="month-view" flex
  on:mousewheel={event => catchErrors(() => onScrollWheel(event))}>
  <hbox class="range-header">
    <slot name="top-left" />
    <DateRange bind:date={start} dateInterval={showDays} />
    <hbox flex />
    <slot name="top-right" />
  </hbox>
  <grid flex class="month"
    style="--selected-calendar-color: {$selectedCalendar?.color ?? "black"}"
    on:swipeleft={onNextMonth}
    on:swiperight={onPreviousMonth}
    on:swipeup={onNextMonth}
    on:swipedown={onPreviousMonth}
    >
    {#each weekDays as day}
      <hbox class="weekday">
        {day.toLocaleDateString(getDateTimeLocale(), { weekday: "short" })}
      </hbox>
    {/each}
    {#each weeks as week}
      <WeekRow days={week} events={filteredEvents}
        on:celldblclick={(param) => newEventMenu.openMenu(param.detail.mouseEvent, param.detail.start)} />
    {/each}
  </grid>
</vbox>

<NewEventMenu bind:this={newEventMenu} />

<script lang="ts">
  import type { Event } from "../../../logic/Calendar/Event";
  import WeekRow from "./WeekRow.svelte";
  import DateRange from "../DateRange.svelte";
  import NewEventMenu from "../NewEventMenu.svelte";
  import { selectedCalendar } from "../selected";
  import { getWeekDays } from "../../Util/date";
  import { catchErrors } from "../../Util/error";
  import { getDateTimeLocale } from "../../../l10n/l10n";
  import type { Collection } from "svelte-collections";

  export let start: Date;
  export let events: Collection<Event>;
  export let showDays = 35;

  let weeks: Date[][] = [];
  let weekDays: Date[] = [];
  let filteredEvents: Collection<Event>;
  let newEventMenu: NewEventMenu;
  $: start, showDays, setDays();
  function setDays() {
    weekDays = getWeekDays(start);
    if (showDays == 35) {
      while (weekDays[6].getDate() > 7) {
        start.setDate(start.getDate() - 7);
        weekDays = getWeekDays(start);
      }
    }
    let startTime = weekDays[0]; // Always start with Monday
    let filterStart = new Date(startTime);
    weeks = [];
    for (let i = 0; i < showDays; i++) {
      if (i % 7 == 0) {
        weeks.push([]);
      }
      weeks[weeks.length - 1].push(new Date(startTime));
      startTime.setDate(startTime.getDate() + 1)
    }
    let filterEnd = startTime;
    filteredEvents = events.filterObservable(ev => ev.startTime && ev.startTime < filterEnd && filterStart < ev.endTime);
  }

  function onScrollWheel(event: WheelEvent) {
    const upDown = event.deltaY > 0 ? 1 : -1;
    start.setDate(start.getDate() + showDays * upDown);
    start = start;
  }

  // <copied from="DateRange.svelte">
  function onNextMonth() {
    start.setDate(start.getDate() + (showDays == 35 ? 42 : showDays));
    start = start;
  }
  function onPreviousMonth() {
    start.setDate(start.getDate() - (showDays == 35 ? 28 : showDays));
    start = start;
  }
  // </copied>
</script>

<style>
  grid.month {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr 1fr 1fr 1fr;
    grid-template-rows: max-content;
    grid-auto-rows: minmax(0, 1fr);
    container-type: size;
  }
  .weekday {
    border-inline-start: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    padding: 6px 8px;
    color: var(--fg-muted);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
</style>
