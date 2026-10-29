<hbox class="new-event-button">
  {#if haveMultipleCalendars}
    <SplitButton
      label={$t`New event`}
      icon={AddToCalendarIcon}
      primary
      onClick={() => createNewEvent($selectedCalendar, $selectedDate, false)}
      placement="bottom-start"
      >
      {#each $shownCalendars.each as calendar}
        <NewEventMenuItem {calendar} startTime={$selectedDate} exact={false} />
      {/each}
    </SplitButton>
  {:else}
    <Button
      label={$t`New event`}
      icon={AddToCalendarIcon}
      classes="primary"
      onClick={() => createNewEvent($selectedCalendar, $selectedDate, false)}
      />
  {/if}
</hbox>

<script lang="ts">
  import { createNewEvent } from "../../frontend/Calendar/event";
  import { selectedCalendar, selectedDate, shownCalendars } from "../../frontend/Calendar/selected";
  import NewEventMenuItem from "../../frontend/Calendar/NewEventMenuItem.svelte";
  import SplitButton from "../Shared/SplitButton.svelte";
  import Button from "../../frontend/Shared/Button.svelte";
  import AddToCalendarIcon from "lucide-svelte/icons/plus";
  import { t } from "../../l10n/l10n";

  $: haveMultipleCalendars = $shownCalendars.length > 1;
</script>

<style>
  .new-event-button {
    flex: none;
  }
  @container calendar-pane (max-width: 600px) {
    .new-event-button :global(.button.primary .label),
    .new-event-button :global(.button.primary .gap) {
      display: none;
    }
  }
</style>
