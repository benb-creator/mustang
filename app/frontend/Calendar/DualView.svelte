<SplitterBidirectional horizontal={$appGlobal.isSmall} initialSecondRatio={1} firstMinPx={200} secondMinPx={200}>
  <svelte:component this={weekView} bind:start={$selectedDate} {events} showDays={2} slot="first" enlargeSelectedDay={true}>
    <slot name="top-left" slot="top-left" />
  </svelte:component>
  <svelte:component this={monthView} {start} {events} showDays={35} slot="second">
    <slot name="top-right" slot="top-right" />
  </svelte:component>
</SplitterBidirectional>

<script lang="ts">
  import type { Event } from "../../logic/Calendar/Event";
  import type { Collection } from "svelte-collections";
  import type { Component } from "svelte";
  import { selectedDate } from "./selected";
  import { appGlobal } from "../../logic/app";
  import WeekView from "./DayView/WeekView.svelte";
  import MonthView from "./MonthView/MonthView.svelte";
  import SplitterBidirectional from "../Shared/SplitterBidirectional.svelte";

  export let start: Date;
  export let events: Collection<Event>;
  /** As in <MainView> */
  export let weekView: Component<any> = WeekView;
  export let monthView: Component<any> = MonthView;
</script>
