<button class="row-button" class:accent on:click={event => catchErrors(() => onClick(event))}>
  {#if icon}
    <hbox class="icon">
      {#if typeof(icon) == "string"}
        <Icon data={icon} size="22px" />
      {:else}
        <svelte:component this={icon} size="22px" />
      {/if}
    </hbox>
  {/if}
  <hbox class="label font-normal" flex>
    {label}
  </hbox>
  {#if !accent}
    <hbox class="go-icon">
      <GoIcon size="20px"/>
    </hbox>
  {/if}
</button>

<script lang="ts">
  import { catchErrors } from "../../Util/error";
  import Icon from "../../Shared/Icon.svelte";
  import GoIcon from "lucide-svelte/icons/chevron-right";
  import type { ConstructorOfATypedSvelteComponent } from "svelte";

  export let label: string;
  export let icon: ConstructorOfATypedSvelteComponent | string | null = null;
  export let onClick: (event: Event) => void;
  /** An action, like "New account", instead of a page to go to */
  export let accent = false;
</script>

<style>
  .row-button {
    display: flex;
    align-items: center;
    width: 100%;
    min-height: 52px;
    padding: 8px 16px;
    border: none;
    border-radius: 0;
    background-color: var(--main-bg);
    color: var(--main-fg);
    text-align: start;
    transition: background-color 120ms ease-out;
  }
  .row-button:active {
    background-color: var(--hover-bg);
    color: var(--hover-fg);
    transition: none;
  }
  .row-button:not(:last-child) {
    box-shadow: inset 0 -1px 0 var(--border);
  }
  .icon {
    flex: none;
    width: 24px;
    margin-inline-end: 16px;
    align-items: center;
    justify-content: center;
    opacity: 75%;
  }
  .label {
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .go-icon {
    flex: none;
    margin-inline-start: 8px;
    opacity: 40%;
  }
  :global([dir="rtl"]) .go-icon {
    transform: scaleX(-1);
  }
  .accent {
    color: var(--selected-bg);
  }
  .accent .icon {
    opacity: 100%;
  }
</style>
