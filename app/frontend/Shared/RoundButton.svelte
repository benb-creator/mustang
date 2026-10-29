<button on:click on:dblclick on:click={myOnClick}
  title={typeof(disabled) == "string" ? disabled : tooltip ?? label}
  class="button {classes}"
  class:filled class:border
  class:selected
  disabled={isDisabled} class:disabled={isDisabled} class:busy={running}
  {tabindex}
  style="--padding: {padding}"
  >
  <hbox class="icon">
    {#if loading}
      <Spinner size={iconSize} />
    {:else if typeof(icon) == "string"}
      {#if icon.startsWith("data:")}
        <img src={icon} width={iconSize} height={iconSize} alt={label} />
      {:else if icon.includes("<svg")}
        <Icon data={icon} size={iconSize} />
      {:else}
        <!-- Unknown icon file -->No
      {/if}
    {:else if icon}
      <svelte:component this={icon} size={iconSize} />
    {:else}
      <slot name="icon" />
    {/if}
  </hbox>
</button>

<script lang="ts">
  import { showError } from '../Util/error';
  import Icon from 'svelte-icon/Icon.svelte';
  import Spinner from './Spinner.svelte';
  import type { ConstructorOfATypedSvelteComponent } from 'svelte';

  export let label: string = null;
  /** Default to the label */
  export let tooltip: string = null;
  export let icon: ConstructorOfATypedSvelteComponent | string = null;
  export let classes = "";
  export let iconSize =
    classes?.includes("create") ? "18px" :
    classes?.includes("large") ? "20px" :
    "16px";
  export let padding =
    classes?.includes("create") ? "8px" :
    classes?.includes("large") ? "10px" :
    classes?.includes("small") ? "4px" :
    classes?.includes("smallest") ? "2px" :
    "8px";
  export let filled = classes?.includes("create");
  export let border = true;
  export let disabled: string | boolean = false;
  export let selected = false;
  export let tabindex = null;
  export let onClick: (event: Event) => void = null;
  export let errorCallback = showError;
  export let loadDelayMS = 500; // ms before showing the spinner

  let loading = false;
  let running = false;
  $: isDisabled = !!disabled || running;
  async function myOnClick(event: Event) {
    if (!(onClick && typeof(onClick) == "function")) {
      return;
    }
    event.stopPropagation();
    event.preventDefault();
    running = true;
    let loadTimeout = setTimeout(() => {
      loading = true;
    }, loadDelayMS);
    try {
      await onClick(event);
    } catch (ex) {
      errorCallback(ex);
    } finally {
      clearTimeout(loadTimeout);
      loading = false;
      running = false;
    }
  }
</script>

<style>
  button {
    border: 1px solid transparent;
    border-radius: var(--button-radius);
    padding: var(--padding);

    flex-direction: row;
    display: flex;
    align-items: center;
    justify-content: center;

    background-color: var(--button-bg);
    color: var(--button-fg);
  }
  button.border {
    border: 1px solid var(--button-border);
  }
  .filled:not(:hover):not(.disabled) {
    background-color: var(--inverted-bg);
    color: var(--inverted-fg);
    border: none;
    padding: calc(var(--padding) + 1px);
    stroke-width: 2px;
  }
  :global(svg) {
    stroke: currentColor;
  }
  .filled:not(:hover) :global(svg) {
    stroke: currentColor;
  }
  .icon {
    margin-inline-end: 0px;
  }
  .disabled {
    opacity: 50%;
  }
  button.button:hover:not(.disabled) {
    background-color: var(--hover-bg);
    color: var(--hover-fg);
    border: 1px solid transparent;
  }
  button.button.filled:hover:not(.disabled) {
    background-color: var(--button-filled-hover-bg);
    color: var(--button-filled-hover-fg);
  }
  .selected:not(.disabled) {
    background-color: var(--selected-bg);
    color:  var(--selected-fg);
  }
  .selected:hover:not(.disabled) {
    background-color: var(--selected-hover-bg);
    color: var(--selected-hover-fg);
  }
  button.border.secondary {
    border-color: var(--button-secondary-line);
  }
  button.plain {
    background-color: transparent;
  }
  :global(.fresh) .button {
    box-sizing: border-box;
    min-width: var(--icon-button-size);
    min-height: var(--icon-button-size);
    padding: 0;
    border: 1px solid transparent;
    border-radius: var(--radius-m);
    background-color: transparent;
    background-image: none;
    color: var(--fg-2);
    cursor: pointer;
    transition: background-color var(--motion-fast) var(--motion-ease), border-color var(--motion-fast) var(--motion-ease), color var(--motion-fast) var(--motion-ease);
  }
  :global(.fresh) .button.border {
    border-color: var(--border-control);
    background-color: var(--btn-sec-bg);
    color: var(--fg-1);
  }
  :global(.fresh) .button.plain {
    border-color: transparent;
    background-color: transparent;
    color: var(--fg-2);
  }
  :global(.fresh) .button.small {
    min-width: var(--icon-button-size-s);
    min-height: var(--icon-button-size-s);
  }
  :global(.fresh) .button.smallest {
    min-width: 20px;
    min-height: 20px;
  }
  :global(.fresh) .button.large {
    min-width: var(--control-height-l);
    min-height: var(--control-height-l);
  }
  :global(.fresh) .button.filled:not(.disabled) {
    padding: 0;
    border: 1px solid var(--accent);
    background-color: var(--accent);
    color: var(--fg-on-accent);
  }
  :global(.fresh) .button.danger {
    color: var(--danger-fg);
  }
  :global(.fresh) .button.button:hover:not(.disabled) {
    background-image: linear-gradient(var(--row-hover), var(--row-hover));
    color: var(--fg-1);
  }
  :global(.fresh) .button.button.border:hover:not(.disabled) {
    border: 1px solid var(--fg-3);
    background-color: var(--btn-sec-bg);
  }
  :global(.fresh) .button.button.plain:hover:not(.disabled) {
    border: 1px solid transparent;
    background-color: transparent;
  }
  :global(.fresh) .button.button:active:not(.disabled) {
    background-image: linear-gradient(var(--row-press), var(--row-press));
  }
  :global(.fresh) .button.button.filled:hover:not(.disabled) {
    border-color: var(--accent-hover);
    background-color: var(--accent-hover);
    background-image: none;
    color: var(--fg-on-accent);
  }
  :global(.fresh) .button.button.danger:hover:not(.disabled) {
    border-color: transparent;
    background-color: var(--danger-tint);
    background-image: none;
    color: var(--danger-fg);
  }
  :global(.fresh) .button.selected:not(.disabled),
  :global(.fresh) .button.button.selected:hover:not(.disabled) {
    border-color: transparent;
    background-color: var(--accent-tint);
    background-image: none;
    color: var(--accent-fg);
  }
  :global(.fresh) .button.disabled:not(.busy) {
    opacity: 1;
    color: var(--fg-disabled);
    cursor: default;
  }
  :global(.fresh) .button.border.disabled:not(.busy) {
    border-color: var(--fill-subtle);
    background-color: var(--fill-subtle);
  }
  :global(.fresh) .button.busy {
    opacity: 1;
    cursor: progress;
  }
</style>
