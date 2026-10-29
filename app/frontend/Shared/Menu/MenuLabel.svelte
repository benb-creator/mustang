<hbox class="menuitem {classes}"
  title={tooltip}
  bind:this={menuItemE}
  >
  {#if label}
    <hbox class="label font-small">{label}</hbox>
  {:else}
    <slot />
  {/if}
</hbox>

<script lang="ts">
  export let label: string = null;
  export let tooltip: string = "";
  export let classes = "";

  let menuItemE: HTMLDivElement;
</script>

<style>
  .menuitem {
    align-items: center;
    padding: 7px 14px;
  }
  .label {
    white-space: nowrap;
    opacity: 50%;
  }
  :global(.fresh) .menuitem {
    padding: 6px 12px 2px;
  }
  :global(.fresh) .menuitem .label {
    opacity: 1;
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-weight: 600;
    color: var(--fg-3);
  }
</style>
