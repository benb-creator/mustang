{#if suggestion?.isOpen && position}
  <vbox class="text-block-suggestions" style="left: {position.left}px; top: {position.bottom + 4}px">
    {#each suggestion.matches as block, i}
      <button class="suggestion" class:selected={i == suggestion.selectedIndex}
        tabindex="-1"
        on:mousedown|preventDefault
        on:click={() => onInsert(block)}>
        <TextBlockLabel {block} />
      </button>
    {/each}
    <hbox class="hint font-smallest">{$t`Enter to insert, Escape to close`}</hbox>
  </vbox>
{/if}

<script lang="ts">
  import { TextBlockSuggestion } from "./TextBlockShortcut";
  import TextBlockLabel from "./TextBlockLabel.svelte";
  import type { TextBlock } from "../../../../logic/Mail/TextBlock/TextBlock";
  import { t } from "../../../../l10n/l10n";
  import type { Editor } from "@tiptap/core";

  /** Needs the `TextBlockShortcut` extension */
  export let editor: Editor;

  $: suggestion = editor && !editor.isDestroyed ? TextBlockSuggestion.of(editor.state) : null;
  $: position = suggestion?.isOpen ? editor.view.coordsAtPos(suggestion.range.from) : null;

  function onInsert(block: TextBlock) {
    editor.chain().focus().insertTextBlock(block, suggestion.range).run();
  }
</script>

<style>
  .text-block-suggestions {
    position: fixed;
    z-index: 100;
    min-width: 15em;
    max-width: 30em;
    max-height: 20em;
    overflow-y: auto;
    padding: 4px;
    background-color: var(--leftbar-bg);
    color: var(--leftbar-fg);
    border-radius: var(--border-radius);
    box-shadow: 2.281px 1.14px 9.123px 0px rgba(var(--shadow-color), 20%);
  }
  .suggestion {
    display: flex;
    padding: 4px 8px;
    border: none;
    border-radius: 3px;
    background-color: transparent;
    color: inherit;
    text-align: start;
  }
  .suggestion:hover {
    background-color: var(--hover-bg);
    color: var(--hover-fg);
  }
  .suggestion.selected {
    background-color: var(--selected-bg);
    color: var(--selected-fg);
  }
  .hint {
    justify-content: end;
    padding: 4px 8px 0px 8px;
    opacity: 60%;
  }
</style>
