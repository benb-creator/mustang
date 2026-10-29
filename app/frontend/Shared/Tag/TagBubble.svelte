<hbox class="tag font-smallest"
  style="--color: {$tag.color}"
  on:click
  class:selected={selected == true}
  class:partial={selected === null}
  class:unselected={selected == false}
  >
  {$tag.name}

  <hbox class="buttons-right">
    <slot name="tag-button" {tag} />
  </hbox>
</hbox>

<script lang="ts">
  import type { Tag } from "../../../logic/Abstract/Tag";

  export let tag: Tag;
  /** true = all objects have this tag, null = only some of them,
   * false = none of them, undefined = tags are not being set here */
  export let selected: boolean | null | undefined = undefined;
</script>

<style>
  .tag {
    min-height: 16px;
    border-radius: 8px;
    background-color: var(--color);
    color: white;
    border: 1px solid transparent;
    padding-inline-start: 8px;
    padding-inline-end: 8px;
    margin: 2px 2px;
  }
  .tag:not(:hover) :global(.button) {
    visibility: hidden;
  }
  .tag.unselected {
    background-color: color-mix(in srgb, var(--color) 30%, transparent);
    color: var(--button-fg);
  }
  .tag.selected {
    border: 1px solid var(--button-border);
  }
  .tag.partial {
    border: 1px dashed var(--button-border);
    opacity: 75%;
  }
  .buttons-right :global(button) {
    align-self: center;
    margin-inline-start: -8px;
    margin-inline-end: -6px;
  }
  :global(.fresh) .tag {
    align-items: center;
    gap: 4px;
    box-sizing: border-box;
    height: 20px;
    min-height: 20px;
    margin: 2px;
    padding: 0 6px;
    border: none;
    border-radius: var(--radius-s);
    background-color: var(--fill-subtle);
    color: var(--fg-1);
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-weight: 500;
    white-space: nowrap;
  }
  :global(.fresh) .tag::before {
    content: "";
    flex: none;
    width: 8px;
    height: 8px;
    border-radius: 2px;
    background-color: var(--color);
  }
  :global(.fresh) .tag.selected,
  :global(.fresh) .tag.partial,
  :global(.fresh) .tag.unselected {
    cursor: pointer;
  }
  :global(.fresh) .tag.selected {
    border: none;
    background-color: var(--accent-tint);
    box-shadow: inset 0 0 0 1px var(--accent-border);
  }
  :global(.fresh) .tag.partial {
    border: none;
    opacity: 1;
    background-color: transparent;
    outline: 1px dashed var(--accent-border);
    outline-offset: -1px;
  }
  :global(.fresh) .tag.unselected {
    background-color: transparent;
    box-shadow: inset 0 0 0 1px var(--border-control);
    color: var(--fg-2);
  }
  :global(.fresh) .tag:hover.unselected,
  :global(.fresh) .tag:hover.partial {
    background-color: var(--row-hover);
  }
  :global(.fresh) .buttons-right :global(button) {
    margin-inline: 0 -4px;
  }
</style>
