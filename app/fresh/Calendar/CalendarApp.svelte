<hbox flex class="calendar-app" class:has-event={!!$selectedEvent}>
  {#if $isCalendarListOpen}
    <CalendarList />
  {/if}
  <Splitter
    initialRightRatio={0.25}
    rightMinWidth={250}
    >
    <vbox flex class="main" slot="left">
      <MainView events={shownCalendarEvents} bind:start={$startDate} dateInterval={$dateIntervalSetting.value}
        listView={ListViewWithSearch} weekView={WeekView} monthView={MonthView}>
        <TitleBarLeft slot="top-left" />
        <TitleBarRight bind:dateInterval={dateIntervalSetting.value} slot="top-right" />
      </MainView>
    </vbox>
    <vbox flex class="details" slot="right">
      {#if $selectedEvent}
        <ShowEvent event={$selectedEvent} />
      {/if}
    </vbox>
  </Splitter>
</hbox>

<script lang="ts">
  import { isCalendarListOpen, selectedCalendar, selectedEvent, shownCalendarEvents, startDate, type DateInterval } from "../../frontend/Calendar/selected";
  import { appGlobal } from "../../logic/app";
  import CalendarList from "./CalendarList.svelte";
  import MainView from "../../frontend/Calendar/MainView.svelte";
  import ListViewWithSearch from "./ListView/ListViewWithSearch.svelte";
  import WeekView from "./DayView/WeekView.svelte";
  import MonthView from "./MonthView/MonthView.svelte";
  import TitleBarLeft from "./TitleBarLeft.svelte";
  import TitleBarRight from "./TitleBarRight.svelte";
  import ShowEvent from "../../frontend/Calendar/DisplayEvent/ShowEvent.svelte";
  import Splitter from "../../frontend/Shared/Splitter.svelte";
  import { getLocalStorage } from "../../frontend/Util/LocalStorage";

  // <copied from="../../frontend/Calendar/CalendarApp.svelte">
  $: if (!$selectedCalendar) { $selectedCalendar = appGlobal.calendars.first; }

  let dateIntervalSetting = getLocalStorage("calendar.view", 2 as DateInterval);
  // </copied>
</script>

<style>
  .calendar-app {
    position: relative;
    min-width: 0;
    min-height: 0;
  }
  .main {
    min-width: 0;
    min-height: 0;
    border-block-start: 1px solid var(--border);
    background-color: var(--l3-bg);
    color: var(--l3-fg);
  }
  .details {
    min-width: 0;
    min-height: 0;
    border-block-start: 1px solid var(--border);
    border-inline-start: 1px solid var(--border);
    background-color: var(--l3-bg);
    color: var(--l3-fg);
    container-type: inline-size;
  }
  .calendar-app:not(.has-event) > :global(.splitter > .right),
  .calendar-app:not(.has-event) > :global(.splitter > .splitter-bar) {
    display: none;
  }
  @container app (max-width: 760px) {
    .calendar-app.has-event > :global(.splitter > .right) {
      position: absolute;
      inset-block: 0;
      inset-inline-end: 0;
      z-index: 3;
      width: min(360px, 90%);
      /* Splitter sets the min-width inline */
      min-width: 0 !important;
      box-shadow: var(--shadow-pop);
    }
    .calendar-app.has-event > :global(.splitter > .splitter-bar) {
      display: none;
    }
  }
</style>
