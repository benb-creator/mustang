{#if dateInterval == 0 || $globalSearchTerm}
  <svelte:component this={listView} {events}>
    <slot name="top-left" slot="top-left" />
    <slot name="top-right" slot="top-right" />
  </svelte:component>
{:else if dateInterval == 1}
  <svelte:component this={weekView} bind:start {events} showDays={1}>
    <slot name="top-left" slot="top-left" />
    <slot name="top-right" slot="top-right" />
  </svelte:component>
{:else if dateInterval > 3 && dateInterval <= 7}
  <svelte:component this={weekView} bind:start {events} showDays={dateInterval} enlargeSelectedDay={true}>
    <slot name="top-left" slot="top-left" />
    <slot name="top-right" slot="top-right" />
  </svelte:component>
{:else if dateInterval == 28}
  <svelte:component this={monthView} bind:start {events} showDays={28}>
    <slot name="top-left" slot="top-left" />
    <slot name="top-right" slot="top-right" />
  </svelte:component>
{:else if dateInterval == 31}
  <svelte:component this={monthView} bind:start {events}>
    <slot name="top-left" slot="top-left" />
    <slot name="top-right" slot="top-right" />
  </svelte:component>
{:else if dateInterval == 2}
  <DualView bind:start {events} {weekView} {monthView}>
    <slot name="top-left" slot="top-left" />
    <slot name="top-right" slot="top-right" />
  </DualView>
{:else}
  <svelte:component this={weekView} bind:start {events} showDays={7}>
    <slot name="top-left" slot="top-left" />
    <slot name="top-right" slot="top-right" />
  </svelte:component>
{/if}

<script lang="ts">
  import type { Event } from "../../logic/Calendar/Event";
  import type { DateInterval } from "./selected";
  import { globalSearchTerm } from "../AppsBar/selectedApp";
  import WeekView from "./DayView/WeekView.svelte";
  import MonthView from "./MonthView/MonthView.svelte";
  import DualView from "./DualView.svelte";
  import ListViewWithSearch from "./ListView/ListViewWithSearch.svelte";
  import type { Collection } from "svelte-collections";
  import type { Component } from "svelte";

  export let start: Date;
  export let events: Collection<Event>;
  export let dateInterval: DateInterval;
  /** The components that show the views, with the same props and slots as these defaults.
   * Another UI passes its own. */
  export let listView: Component<any> = ListViewWithSearch;
  export let weekView: Component<any> = WeekView;
  export let monthView: Component<any> = MonthView;
</script>
