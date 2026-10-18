<hbox class="new-event-button">
  {#if haveMultipleCalendars}
    <ButtonMenu bind:isMenuOpen>
      <Button
        classes="add-button create filled"
        label={$t`New event`}
        icon={AddToCalendarIcon}
        iconSize="16px"
        slot="control"
        onClick={() => isMenuOpen = !isMenuOpen}
        />
      {#each $shownCalendars.each as calendar}
        <NewEventMenuItem {calendar} startTime={$selectedDate} exact={false} />
      {/each}
    </ButtonMenu>
  {:else}
    <Button
      classes="add-button create filled"
      label={$t`New event`}
      icon={AddToCalendarIcon}
      iconSize="16px"
      onClick={() => createNewEvent($selectedCalendar, $selectedDate, false)}
      />
  {/if}
</hbox>

<script lang="ts">
  import { createNewEvent } from "./event";
  import { selectedCalendar, selectedDate, shownCalendars } from "./selected";
  import ButtonMenu from "../Shared/Menu/ButtonMenu.svelte";
  import NewEventMenuItem from "./NewEventMenuItem.svelte";
  import Button from "../Shared/Button.svelte";
  import AddToCalendarIcon from "lucide-svelte/icons/plus";
  import { t } from "../../l10n/l10n";

  $: haveMultipleCalendars = $shownCalendars.length > 1;
  let isMenuOpen = false;
</script>

<style>
  .new-event-button {
    align-items: center;
  }
  .new-event-button :global(.add-button) {
    align-items: center;
    justify-content: center;
    position: relative;
    white-space: nowrap;
  }
</style>
