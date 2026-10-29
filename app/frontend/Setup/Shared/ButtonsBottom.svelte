<hbox class="buttons">
  <slot />
  {#if showReset}
    <Button label={$t`Start over`} classes="secondary reset"
      onClick={onReset}
      {errorCallback}
      />
  {/if}
  {#if canCancel}
    <Button label={$t`Cancel`} classes="secondary cancel"
      onClick={onCancel}
      {errorCallback}
      />
  {/if}
  <hbox flex class="spacer" />
  {#if showContinue}
    <Button label={labelContinue ?? $t`Next`} classes="filled large"
      disabled={!canContinue}
      onClick={onContinue}
      {errorCallback}
      />
  {/if}
</hbox>

<script lang="ts">
  import Button from "../../Shared/Button.svelte";
  import { t } from "../../../l10n/l10n";

  export let onContinue: (ex: Event) => void = undefined;
  export let onCancel: (ex: Event) => void = undefined;
  export let onReset: (ex: Event) => void = undefined;
  export let errorCallback: (ex: Error) => void = undefined;
  export let canContinue: boolean;
  export let canCancel = false;
  export let showReset = false;
  export let showContinue = true;
  export let labelContinue: string | null = null;
</script>

<style>
  .buttons {
    align-items: end;
    justify-content: end;
    margin-block-start: 32px;
  }
  .buttons :global(> *) {
    margin-inline-end: 8px;
  }
  .buttons :global(button.secondary .label) {
    margin-left: 5px;
    margin-right: 5px;
  }
  .buttons :global(button.disabled) {
    opacity: 40%;
  }
  .buttons :global(button.secondary) {
    background-color: inherit;
    padding: 3px 8px;
    font-weight: 300;
  }
  .buttons :global(button.secondary:not(.disabled)) {
    opacity: 85%;
  }
  .buttons :global(button.secondary) {
    border-color: #BBBBBB;
  }
  @media (prefers-color-scheme: dark) {
    .buttons :global(button.secondary) {
      border-color: #222222;
    }
  }
  :global(.fresh) .buttons {
    align-items: center;
    gap: 8px;
    margin-block-start: 24px;
  }
  :global(.fresh) .buttons :global(> *) {
    margin-inline-end: 0;
  }
  :global(.fresh) .buttons :global(button.secondary) {
    padding: 0 12px;
    border-color: var(--border-control);
    background-color: var(--btn-sec-bg);
    font-weight: 500;
  }
  :global(.fresh) .buttons :global(button.secondary:not(.disabled)) {
    opacity: 1;
  }
  :global(.fresh) .buttons :global(button.secondary .label) {
    margin: 0;
  }
  :global(.fresh) .buttons :global(.button.reset),
  :global(.fresh) .buttons :global(.button.cancel) {
    order: -2;
  }
  :global(.fresh) .spacer {
    order: -1;
  }
</style>
