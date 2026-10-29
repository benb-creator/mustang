<vbox class="dialpad">
  <grid class="numbers">
    {#each ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"] as digit}
      <RoundButton
        label={digit.toString()}
        onClick={() => onSendNumber(digit)}
        >
        <hbox class="digit font-large" slot="icon">{digit}</hbox>
      </RoundButton>
    {/each}
  </grid>
</vbox>

<script lang="ts">
  import RoundButton from "../../../Shared/RoundButton.svelte";
  import { createEventDispatcher } from 'svelte';
  const dispatchEvent = createEventDispatcher<{ digit: string }>();

  function onSendNumber(digit: string) {
    dispatchEvent("digit", digit);
  }
</script>

<style>
  grid.numbers {
    grid-template-columns: auto auto auto;
    gap: 8px;
  }
  .numbers :global(button) {
    width: 48px;
    height: 48px;
  }
  .digit {
    opacity: 50%;
  }
  :global(.fresh) .numbers :global(.button.button) {
    width: 48px;
    height: 48px;
    border-radius: var(--radius-m);
  }
  :global(.fresh) .digit {
    opacity: 1;
    font-variant-numeric: tabular-nums;
    color: var(--fg-1);
  }
</style>
