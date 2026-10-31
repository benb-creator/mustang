<vbox flex class="calendar-app">
  <hbox flex>
    {#if $isCalendarListOpen}
      <CalendarList />
    {/if}
    <Splitter
      initialRightRatio={0.25}
      rightMinWidth={250}
      hasRight={!appGlobal.isMobile}
      >
      <vbox flex class="main" slot="left" class:mobile={$appGlobal.isMobile}>
        <MainView events={shownCalendarEvents} bind:start={$startDate} dateInterval={$dateIntervalSetting.value}>
          <hbox slot="top-left">
            {#if !$appGlobal.isMobile}
              <TitleBarLeft />
            {/if}
          </hbox>
          <TitleBarRight bind:dateInterval={dateIntervalSetting.value} slot="top-right" />
        </MainView>
      </vbox>
      <vbox flex class="sidebar" slot="right">
        {#if $selectedEvent && !appGlobal.isMobile}
          <ShowEvent event={$selectedEvent} />
        {:else}
          <!--<TaskList />-->
        {/if}
      </vbox>
    </Splitter>
  </hbox>
  {#if $appGlobal.isMobile}
    <CalendarViewBarM />
  {/if}
</vbox>

<script lang="ts">
  import { isCalendarListOpen, selectedCalendar, selectedEvent, shownCalendarEvents, startDate, type DateInterval } from "./selected";
  import { appGlobal } from "../../logic/app";
  import CalendarList from "./CalendarList.svelte";
  import MainView from "./MainView.svelte";
  import CalendarViewBarM from "./MonthView/CalenderViewBarM.svelte";
  import TitleBarLeft from "./TitleBarLeft.svelte";
  import TitleBarRight from "./TitleBarRight.svelte";
  import ShowEvent from "./DisplayEvent/ShowEvent.svelte";
  import Splitter from "../Shared/Splitter.svelte";
  import { getLocalStorage } from "../Util/LocalStorage";

  $: if (!$selectedCalendar) { $selectedCalendar = appGlobal.calendars.first; }

  let dateIntervalSetting = getLocalStorage("calendar.view", 2 as DateInterval);
</script>

<style>
  .main {
    margin: 0px 16px 16px 16px;
  }
  .main :global(.range-header) {
    height: 58px;
    align-items: center;
  }
  .main.mobile {
    margin: 0px;
  }
  .main.mobile :global(.range-header) {
    flex: none;
    height: 48px;
    padding-inline: 12px 4px;
    container-type: inline-size;
  }
  .main.mobile :global(.range-header .date-range-header) {
    order: -1;
    align-self: center;
    min-width: 0;
    margin: 0px;
  }
  .main.mobile :global(.range-header .date-range) {
    display: block;
    min-width: 0;
    margin-inline: 0px 4px;
    font-size: 20px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  @container (max-width: 379px) {
    .main.mobile :global(.range-header .date-range) {
      font-size: 18px;
    }
  }
  .main.mobile :global(.range-header .today-button) {
    order: 1;
    align-self: center;
    margin: 0px;
  }
  .main.mobile :global(.range-header button.button) {
    min-width: 44px;
    min-height: 44px;
    justify-content: center;
  }
</style>
