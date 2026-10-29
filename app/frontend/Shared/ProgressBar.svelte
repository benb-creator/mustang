<vbox class="progress-bar">
  {#if label || etaLabel}
    <hbox class="labels">
      {#if label}
        <hbox class="label">{label}</hbox>
      {/if}
      <hbox flex />
      {#if etaLabel}
        <hbox class="eta">{etaLabel}</hbox>
      {/if}
    </hbox>
  {/if}
  <progress value={value} max={max || 1}></progress>
</vbox>

<script lang="ts">
  import { t } from "../../l10n/l10n";

  /** Number of items processed so far */
  export let value: number;
  /** Total number of items */
  export let max: number;
  export let label: string = null;
  /** Estimate and show the time remaining */
  export let showETA = true;

  $: etaLabel = showETA ? "" /*calculateETALabel()*/ : "";
  let startTime = new Date();
  function calculateETALabel() {
    let secs = remainingTimeInSec();
    console.log("remaining", secs);
    return secs >= 60
      ? $t`About ${Math.ceil(remainingTimeInSec() / 60)} minutes remaining`
      : $t`About ${Math.ceil(remainingTimeInSec())} seconds remaining`;
  }
  function remainingTimeInSec(): number {
    let elapsedSeconds = (Date.now() - startTime.getTime()) / 1000;
    let secondsPerItem = elapsedSeconds / value;
    let remainingItems = max - value;
    return remainingItems * secondsPerItem;
  }
</script>

<style>
  .progress-bar {
    width: 100%;
  }
  .labels {
    margin-block-end: 2px;
    font-size: 13px;
  }
  .label {
    overflow-wrap: anywhere;
  }
  .eta {
    margin-inline-start: 16px;
    white-space: nowrap;
    opacity: 65%;
  }
  progress {
    width: 100%;
    height: 24px;
    accent-color: var(--selected-bg);
  }
  :global(.fresh) .labels {
    margin-block-end: 4px;
    font-size: var(--text-s);
    line-height: var(--line-s);
    color: var(--fg-2);
  }
  :global(.fresh) .progress-bar progress {
    appearance: none;
    height: 4px;
    border: none;
    border-radius: 2px;
    background-color: var(--border-subtle);
    overflow: hidden;
  }
  :global(.fresh) .progress-bar progress::-webkit-progress-bar {
    border-radius: 2px;
    background-color: var(--border-subtle);
  }
  :global(.fresh) .progress-bar progress::-webkit-progress-value {
    border-radius: 2px;
    background-color: var(--accent);
    transition: inline-size var(--motion-base) var(--motion-ease);
  }
</style>
