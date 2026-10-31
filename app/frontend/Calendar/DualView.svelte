{#if $appGlobal.isMobile}
  <SplitterBidirectional horizontal={true} initialSecondRatio={1} firstMinPx={200} secondMinPx={200}>
    <MonthView {start} {events} showDays={35} slot="first">
      <slot name="top-right" slot="top-right" />
    </MonthView>
    <vbox flex class="day-view" slot="second">
      <WeekView bind:start={$selectedDate} {events} showDays={2} enlargeSelectedDay={true} />
    </vbox>
  </SplitterBidirectional>
{:else}
  <SplitterBidirectional horizontal={$appGlobal.isSmall} initialSecondRatio={1} firstMinPx={200} secondMinPx={200}>
    <WeekView bind:start={$selectedDate} {events} showDays={2} slot="first" enlargeSelectedDay={true}>
      <slot name="top-left" slot="top-left" />
    </WeekView>
    <MonthView {start} {events} showDays={35} slot="second">
      <slot name="top-right" slot="top-right" />
    </MonthView>
  </SplitterBidirectional>
{/if}

<script lang="ts">
  import type { Event } from "../../logic/Calendar/Event";
  import type { Collection } from "svelte-collections";
  import { selectedDate } from "./selected";
  import { appGlobal } from "../../logic/app";
  import WeekView from "./DayView/WeekView.svelte";
  import MonthView from "./MonthView/MonthView.svelte";
  import SplitterBidirectional from "../Shared/SplitterBidirectional.svelte";

  export let start: Date;
  export let events: Collection<Event>;
</script>

<style>
  /* The month above has the header */
  :global(.mobile) .day-view :global(.range-header) {
    display: none;
  }
</style>
