<vbox class="calendar-list">
  <PaneHeader level="l1">
    <NewEventButton />
    <SyncButton iconSize="16px" slot="actions" />
  </PaneHeader>
  <SectionHeader label={$t`Calendars`} level="l1" />
  <vbox class="calendars" flex>
    {#each $calendars.each as calendar (calendar.id)}
      <NavRow label={calendar.name} on:click={() => toggleCalendar(calendar)}>
        <hbox class="calendar-checkbox" slot="icon"
          style="--calendar-color: {calendar.color}"
          on:click|stopPropagation>
          <Checkbox
            toggle={false}
            checked={$shownCalendars.contains(calendar)}
            tooltip={$t`Show this calendar`}
            on:change={event => shownCalendars.show(calendar, event.detail)}
            />
        </hbox>
        <hbox class="actions" slot="actions" on:click|stopPropagation>
          <Button
            label={$t`New event in ${calendar.name}`}
            icon={AddIcon}
            iconOnly
            plain
            classes="small"
            onClick={() => createNewEvent(calendar, $selectedDate, false)}
            />
        </hbox>
      </NavRow>
    {/each}
  </vbox>
</vbox>

<script lang="ts">
  import type { Calendar } from "../../logic/Calendar/Calendar";
  import { selectedDate, shownCalendars } from "../../frontend/Calendar/selected";
  import { createNewEvent } from "../../frontend/Calendar/event";
  import { appGlobal } from "../../logic/app";
  import NewEventButton from "./NewEventButton.svelte";
  import SyncButton from "../../frontend/Calendar/SyncButton.svelte";
  import PaneHeader from "../Shared/PaneHeader.svelte";
  import SectionHeader from "../Shared/SectionHeader.svelte";
  import NavRow from "../Shared/NavRow.svelte";
  import Button from "../../frontend/Shared/Button.svelte";
  import Checkbox from "../../frontend/Shared/Checkbox.svelte";
  import AddIcon from "lucide-svelte/icons/plus";
  import { t } from "../../l10n/l10n";

  let calendars = appGlobal.calendars;

  function toggleCalendar(calendar: Calendar) {
    shownCalendars.show(calendar, !shownCalendars.contains(calendar));
  }
</script>

<style>
  .calendar-list {
    width: 20cqi;
    min-width: 180px;
    container-type: inline-size;
    background-color: var(--l1-bg);
    color: var(--l1-fg);
    box-shadow: inset -1px 0 0 var(--border);
  }
  :global([dir="rtl"]) .calendar-list {
    box-shadow: inset 1px 0 0 var(--border);
  }
  .calendars {
    overflow-y: auto;
    padding-block-end: 8px;
  }
  .calendar-checkbox {
    align-items: center;
  }
  .calendar-checkbox :global(.checkbox label) {
    display: none;
  }
  :global(.fresh) .calendar-list .calendar-checkbox :global(.checkbox.checkbox input:checked) {
    border-color: var(--calendar-color);
    background-color: var(--calendar-color);
  }
  :global(.fresh) .calendar-list .calendar-checkbox :global(.checkbox.checkbox .state-icon-wrapper) {
    color: lch(from var(--calendar-color) calc((49.44 - l) * infinity) 0 0);
  }
  .actions {
    align-items: center;
  }
</style>
