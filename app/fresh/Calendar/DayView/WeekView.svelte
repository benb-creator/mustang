<vbox class="week-view" flex>
  <PaneHeader level="l3">
    <hbox class="range-start" slot="start">
      <slot name="top-left" />
      <Button
        label={$t`Today`}
        tooltip={$t`Go back to today`}
        classes="today-button small"
        onClick={() => start = getToday()}
        />
    </hbox>
    <DateRange bind:date={start} dateInterval={showDays > 3 ? 7 : 1} {showDays} />
    <slot name="top-right" slot="actions" />
  </PaneHeader>
  <DayViewGrid {start} {events} {showDays} {showHours} {defaultFocusHour} {enlargeSelectedDay}
    on:celldblclick={(param) => newEventMenu.openMenu(param.detail.mouseEvent, param.detail.start)}>
    <DayHeader slot="day-header" let:day {day} />
  </DayViewGrid>
</vbox>

<NewEventMenu bind:this={newEventMenu} />

<script lang="ts">
  import type { Event } from "../../../logic/Calendar/Event";
  import type { DateInterval } from "../../../frontend/Calendar/selected";
  import { getToday } from "../../../logic/util/date";
  import DayViewGrid from "../../../frontend/Calendar/DayView/DayViewGrid.svelte";
  import DayHeader from "./DayHeader.svelte";
  import NewEventMenu from "../../../frontend/Calendar/NewEventMenu.svelte";
  import DateRange from "../../../frontend/Calendar/DateRange.svelte";
  import PaneHeader from "../../Shared/PaneHeader.svelte";
  import Button from "../../../frontend/Shared/Button.svelte";
  import type { Collection } from "svelte-collections";
  import { t } from "../../../l10n/l10n";

  export let start: Date;
  export let events: Collection<Event>;
  export let showDays: DateInterval;
  /* Number of hours visible at the same time. Larger range reduces size per hour.
   * Other hours are available on scroll. */
  export let showHours = 10;
  export let defaultFocusHour: number | null = null;
  export let enlargeSelectedDay = false;

  let newEventMenu: NewEventMenu;
</script>

<style>
  .week-view {
    min-width: 0;
    min-height: 0;
    container: calendar-pane / inline-size;
  }
  .range-start {
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
</style>
