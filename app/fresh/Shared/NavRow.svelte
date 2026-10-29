<hbox class="nav-row next-{nextLevel}"
  class:selected
  class:drop-target={dropTarget}
  class:main
  class:has-actions={$$slots.actions}
  style="padding-inline-start: {12 + indent * 16}px"
  title={tooltip ?? label}
  on:click
  on:dblclick
  on:contextmenu
  on:dragenter
  on:dragover
  on:dragleave
  on:drop
  >
  {#if expandable}
    <button class="expander" class:expanded
      on:click={onExpanderClick}
      title={expanded ? $t`Collapse` : $t`Expand`}
      aria-expanded={expanded}
      tabindex={-1}
      >
      <ChevronIcon size="16px" />
    </button>
  {:else if expandable === false}
    <hbox class="expander-space" />
  {/if}
  {#if icon || $$slots.icon}
    <hbox class="icon">
      {#if typeof(icon) == "string"}
        <Icon data={icon} size="16px" />
      {:else if icon}
        <svelte:component this={icon} size="16px" />
      {:else}
        <slot name="icon" />
      {/if}
    </hbox>
  {/if}
  <hbox class="label">
    {#if label}
      {label}
    {:else}
      <slot name="label" />
    {/if}
  </hbox>
  {#if count}
    <hbox class="count">
      {#if countKind == "new"}
        <Badge {count} kind="signal" />
      {:else}
        {count}
      {/if}
    </hbox>
  {/if}
  {#if $$slots.actions}
    <hbox class="actions">
      <slot name="actions" />
    </hbox>
  {/if}
</hbox>

<script lang="ts">
  import Badge from "./Badge.svelte";
  import Icon from "../../frontend/Shared/Icon.svelte";
  import ChevronIcon from "lucide-svelte/icons/chevron-right";
  import { t } from "../../l10n/l10n";

  export let label: string = null;
  export let icon: ConstructorOfATypedSvelteComponent | string = null;
  export let tooltip: string = null;
  export let count: number = 0;
  /** new: unread or newly arrived items, as signal badge.
   * total: number of items, as quiet text */
  export let countKind: "new" | "total" = "new";
  /** Tree depth, 0 = top */
  export let indent = 0;
  /** true: Shows an expander.
   * false: Keeps the expander's space, for a tree item without children.
   * null: No expander space, for a flat list */
  export let expandable: boolean | null = null;
  /** in/out */
  export let expanded = false;
  /** false: The chevron only shows `expanded`, and a click on it reaches the row,
   * e.g. in a FastTree, which opens and closes the items itself */
  export let expanderToggles = true;
  /** The row is an open tab into the pane next to it */
  export let selected = false;
  /** Which level the selected row opens: the list (l2) or directly the content (l3) */
  export let nextLevel: "l2" | "l3" = "l2";
  /** Something is being dragged over the row and can be dropped here */
  export let dropTarget = false;
  /** Top level entry, e.g. a main settings category */
  export let main = false;

  function onExpanderClick(event: MouseEvent) {
    if (!expanderToggles) {
      return;
    }
    event.stopPropagation();
    expanded = !expanded;
  }
</script>

<style>
  .nav-row {
    position: relative;
    isolation: isolate;
    flex: none;
    align-items: center;
    gap: 6px;
    box-sizing: border-box;
    height: var(--nav-row-height);
    min-width: 0;
    padding-inline-end: 12px;
    color: var(--fg-1);
    white-space: nowrap;
    cursor: default;
  }
  .nav-row::before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: -1;
    pointer-events: none;
  }
  .nav-row.main {
    height: 32px;
    font-weight: 600;
  }
  .nav-row:hover:not(.selected)::before {
    background-color: var(--row-hover);
  }
  .nav-row.selected {
    font-weight: 600;
  }
  .nav-row.selected::before {
    background-color: var(--l2-bg);
    box-shadow: inset 0 1px 0 var(--border), inset 0 -1px 0 var(--border);
  }
  .nav-row.selected.next-l3::before {
    background-color: var(--l3-bg);
  }
  .nav-row.drop-target::before {
    background-color: var(--accent-tint);
    box-shadow: inset 0 0 0 1px var(--accent);
  }
  .expander,
  .expander-space {
    flex: none;
    width: 16px;
    height: 16px;
  }
  .expander {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border: none;
    border-radius: var(--radius-s);
    background-color: transparent;
    color: var(--fg-3);
    cursor: pointer;
    transition: transform var(--motion-fast) var(--motion-ease);
  }
  :global([dir="rtl"]) .expander {
    transform: scaleX(-1);
  }
  .expander.expanded {
    transform: rotate(90deg);
  }
  .expander:hover {
    color: var(--fg-1);
  }
  .icon {
    flex: none;
    align-items: center;
    justify-content: center;
    color: var(--fg-2);
  }
  .nav-row.selected .icon {
    color: var(--fg-1);
  }
  .label {
    display: block;
    flex: 1 1 0;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .count {
    flex: none;
    align-items: center;
    font-size: var(--text-s);
    color: var(--fg-3);
    font-variant-numeric: tabular-nums;
    font-weight: 400;
  }
  .actions {
    flex: none;
    align-items: center;
    gap: 2px;
    margin-inline-end: -6px;
  }
  .nav-row:not(:hover):not(:has(:focus-visible)) .actions {
    position: absolute;
    inset-inline-end: 0;
    opacity: 0;
    pointer-events: none;
  }
  :global(.fast-list) .nav-row:not(.selected):not(:hover):not(:has(:focus-visible)) .actions {
    display: none;
  }
  .nav-row.has-actions:hover .count,
  .nav-row.has-actions:has(:focus-visible) .count {
    display: none;
  }
  :global(.fresh .fast-list .row) > .nav-row,
  :global(.fresh .fast-list .row:not(.selected):hover) > .nav-row,
  :global(.fresh .fast-list .row.selected) > .nav-row,
  :global(.fresh .fast-list .row.selected:hover) > .nav-row,
  :global(.fresh .fast-list .row > *):has(.nav-row),
  :global(.fresh .fast-list .row:not(.selected):hover > *):has(.nav-row),
  :global(.fresh .fast-list .row.selected > *):has(.nav-row),
  :global(.fresh .fast-list .row.selected:hover > *):has(.nav-row) {
    --fg-1: inherit;
    --fg-2: inherit;
    --fg-3: inherit;
    --accent-fg: inherit;
    background-color: transparent;
    color: var(--fg-1);
  }
  @container (max-width: 120px) {
    .nav-row {
      justify-content: center;
      padding-inline: 4px;
    }
    .label,
    .expander,
    .expander-space,
    .actions {
      display: none;
    }
    .count {
      position: absolute;
      top: 1px;
      inset-inline-end: 4px;
    }
  }
</style>
