<hbox class="section-header {level}" class:collapsible>
  {#if collapsible}
    <button class="toggle" class:expanded
      on:click={onToggle}
      title={expanded ? $t`Collapse` : $t`Expand`}
      aria-expanded={expanded}
      >
      <hbox class="chevron">
        <ChevronIcon size="16px" />
      </hbox>
      <hbox class="label">{label}</hbox>
    </button>
  {:else}
    <hbox class="label">{label}</hbox>
  {/if}
  <hbox class="rule" />
  {#if $$slots.actions}
    <hbox class="actions">
      <slot name="actions" />
    </hbox>
  {/if}
</hbox>

<script lang="ts">
  import ChevronIcon from "lucide-svelte/icons/chevron-right";
  import { t } from "../../l10n/l10n";

  export let label: string;
  /** Which pane level the header sits on: navigation, list or content */
  export let level: "l1" | "l2" | "l3" = "l2";
  export let collapsible = false;
  /** Only with `collapsible`
   * in/out */
  export let expanded = true;

  function onToggle() {
    expanded = !expanded;
  }
</script>

<style>
  .section-header {
    flex: none;
    align-items: center;
    gap: 8px;
    min-height: var(--section-header-height);
    padding-inline: 12px;
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-weight: 600;
    color: var(--fg-2);
  }
  .label {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }
  .toggle {
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
    margin-inline-start: -4px;
    padding: 2px 4px;
    border: none;
    border-radius: var(--radius-s);
    background-color: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .toggle:hover {
    background-color: var(--row-hover);
    color: var(--fg-1);
  }
  .toggle:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 0;
  }
  .chevron {
    color: var(--fg-3);
    transition: transform var(--motion-fast) var(--motion-ease);
  }
  :global([dir="rtl"]) .chevron {
    transform: scaleX(-1);
  }
  .toggle.expanded .chevron {
    transform: rotate(90deg);
  }
  .rule {
    flex: 1 0 0;
    min-width: 8px;
    height: 1px;
    background-color: var(--border-subtle);
  }
  .section-header.l1 .rule {
    background-color: var(--border);
  }
  .actions {
    align-items: center;
    gap: 2px;
  }
</style>
