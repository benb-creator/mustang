<hbox class="title">
  <input type="text" placeholder={$t`Title - Enter the topic of the meeting`} bind:value={event.title} class="font-normal"/>
</hbox>

<script lang="ts">
  import type { Event } from "../../../logic/Calendar/Event";
  import { t } from "../../../l10n/l10n";

  export let event: Event;
</script>

<style>
  .title input {
    font-size: 100%;
    font-weight: bold;
    padding: 6px 12px;
    max-width: 40em;
  }
  :global(.fresh) .title input,
  :global(.fresh) .title input:hover {
    box-sizing: border-box;
    width: 100%;
    max-width: 40em;
    height: 40px;
    padding: 0 2px;
    border: none;
    border-bottom: 1px solid var(--border-subtle);
    border-radius: 0;
    background-color: transparent;
    color: var(--fg-1);
    font-size: var(--text-2xl);
    font-weight: 600;
    letter-spacing: -0.01em;
  }
  :global(.fresh) .title input:focus {
    border-bottom: 2px solid var(--accent);
    box-shadow: none;
  }
</style>
