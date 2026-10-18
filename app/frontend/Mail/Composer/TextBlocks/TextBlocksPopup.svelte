<!-- svelte-ignore a11y_no_static_element_interactions -->
<vbox class="text-blocks-popup" class:editing={!!editingBlock} on:keydown={onKeyEscape}>
  {#if editingBlock}
    <TextBlockEdit block={editingBlock}
      on:save={onSaved}
      on:cancel={() => editingBlock = null}
      />
  {:else}
    <TextBlocksList {editor}
      on:edit={event => onEdit(event.detail)}
      on:close={() => dispatchEvent("close")}
      />
  {/if}
</vbox>

<script lang="ts">
  import type { TextBlock } from "../../../../logic/Mail/TextBlock/TextBlock";
  import { textBlocks } from "../../../../logic/Mail/TextBlock/TextBlocks";
  import TextBlocksList from "./TextBlocksList.svelte";
  import TextBlockEdit from "./TextBlockEdit.svelte";
  import type { Editor } from "@tiptap/core";
  import { createEventDispatcher } from "svelte";
  const dispatchEvent = createEventDispatcher<{ close: void }>();

  /** The email text, where the text blocks will be inserted */
  export let editor: Editor;

  let editingBlock: TextBlock | null = null;
  let isNewBlock = false;

  function onEdit(block: TextBlock) {
    isNewBlock = !textBlocks.contains(block);
    editingBlock = block;
  }

  function onSaved() {
    editingBlock = null;
    if (isNewBlock) {
      close();
    }
  }

  function onKeyEscape(event: KeyboardEvent) {
    if (event.key != "Escape") {
      return;
    }
    close();
  }

  function close() {
    editor.commands.focus();
    dispatchEvent("close");
  }
</script>

<style>
  .text-blocks-popup {
    padding: 8px;
    background-color: var(--leftbar-bg);
    color: var(--leftbar-fg);
    border-radius: var(--border-radius);
  }
  .text-blocks-popup.editing {
    padding: 16px 24px;
  }
</style>
