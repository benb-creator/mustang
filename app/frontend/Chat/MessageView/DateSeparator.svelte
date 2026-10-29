{#if message.sent.getDate() != previousMessage?.sent.getDate() }
  <hbox class="date-separator font-small value">
    {longDayFormat.format(message.sent)}
  </hbox>
{/if}

<script lang="ts">
  import type { Message } from "../../../logic/Abstract/Message";

  export let message: Message;
  export let previousMessage: Message = null;

  const longDayFormat = Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
</script>

<style>
  .date-separator {
    width: 40%;
    align-self: center;
    justify-content: center;
    margin: 20px 20px 0px 20px;
    padding: 5px;
    color: var(--offset-fg);
    opacity: 60%; /* TODO Should change only text color */
  }
  :global(.fresh) .date-separator {
    align-self: stretch;
    align-items: center;
    gap: 12px;
    width: auto;
    margin: 20px 24px 4px;
    padding: 0;
    opacity: 1;
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-weight: 600;
    color: var(--fg-2);
  }
  :global(.fresh) .date-separator::before,
  :global(.fresh) .date-separator::after {
    content: "";
    flex: 1 1 0;
    height: 1px;
    background-color: var(--border-subtle);
  }
</style>
