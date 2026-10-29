<ShowCalendarsButton />
{#if !$isCalendarListOpen}
  <NewEventButton />
{/if}

<script lang="ts">
  import { isCalendarListOpen } from "../../frontend/Calendar/selected";
  import ShowCalendarsButton from "../../frontend/Calendar/ShowCalendarsButton.svelte";
  import NewEventButton from "./NewEventButton.svelte";
</script>
