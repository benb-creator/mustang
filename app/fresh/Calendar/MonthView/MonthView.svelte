<MonthView bind:start {events} {showDays}>
  <PaneHeader level="l3" slot="header">
    <hbox class="range-start" slot="start">
      <slot name="top-left" />
    </hbox>
    <DateRange bind:date={start} dateInterval={showDays} />
    <slot name="top-right" slot="actions" />
  </PaneHeader>
</MonthView>

<script lang="ts">
  import type { Event } from "../../../logic/Calendar/Event";
  import MonthView from "../../../frontend/Calendar/MonthView/MonthView.svelte";
  import DateRange from "../../../frontend/Calendar/DateRange.svelte";
  import PaneHeader from "../../Shared/PaneHeader.svelte";
  import type { Collection } from "svelte-collections";

  export let start: Date;
  export let events: Collection<Event>;
  export let showDays = 35;
</script>

<style>
  .range-start {
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
</style>
