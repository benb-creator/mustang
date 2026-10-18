<vbox class="text-blocks-list">
  {#each $sortedBlocks.each as block}
    <hbox class="text-block">
      <button class="insert" on:click={() => onInsert(block)} title={block.text}>
        <TextBlockLabel {block} />
      </button>
      <hbox class="actions">
        <Button
          label={$t`Edit`}
          icon={EditIcon}
          iconOnly
          plain
          onClick={() => onEdit(block)}
          />
        <Button
          label={$t`Delete`}
          icon={DeleteIcon}
          iconOnly
          plain
          onClick={() => onDelete(block)}
          />
      </hbox>
    </hbox>
  {:else}
    <vbox class="empty font-small">
      {$t`Save text that you often write. Then insert it here, or by typing ::keyword in the email.`}
    </vbox>
  {/each}
  <hbox class="add">
    <Button
      label={hasSelection ? $t`Add the selected text as text block` : $t`New text block`}
      icon={AddIcon}
      plain
      onClick={onAdd}
      />
  </hbox>
</vbox>

<script lang="ts">
  import { TextBlock } from "../../../../logic/Mail/TextBlock/TextBlock";
  import { textBlocks } from "../../../../logic/Mail/TextBlock/TextBlocks";
  import TextBlockLabel from "./TextBlockLabel.svelte";
  import Button from "../../../Shared/Button.svelte";
  import AddIcon from "lucide-svelte/icons/plus";
  import EditIcon from "lucide-svelte/icons/pencil";
  import DeleteIcon from "lucide-svelte/icons/trash-2";
  import { gt, t } from "../../../../l10n/l10n";
  import { getHTMLFromFragment, type Editor } from "@tiptap/core";
  import { createEventDispatcher } from "svelte";
  const dispatchEvent = createEventDispatcher<{ edit: TextBlock, close: void }>();

  /** The email text, where the text block will be inserted */
  export let editor: Editor;

  let sortedBlocks = textBlocks.sortBy(block => block.keyword.toLowerCase());
  $: hasSelection = !editor.state.selection.empty;

  function onInsert(block: TextBlock) {
    editor.chain().focus().insertTextBlock(block).run();
    dispatchEvent("close");
  }

  function onEdit(block: TextBlock) {
    dispatchEvent("edit", block);
  }

  async function onDelete(block: TextBlock) {
    if (!confirm(gt`Do you want to delete the text block ::${block.keyword}?`)) {
      return;
    }
    textBlocks.remove(block);
    await textBlocks.save();
  }

  function onAdd() {
    let block = new TextBlock();
    block.html = hasSelection
      ? getHTMLFromFragment(editor.state.selection.content().content, editor.schema)
      : "";
    dispatchEvent("edit", block);
  }
</script>

<style>
  .text-blocks-list {
    width: 28em;
    max-width: 90vw;
    max-height: 60vh;
    overflow-y: auto;
  }
  .text-block {
    align-items: center;
    border-radius: var(--border-radius);
  }
  .text-block:hover {
    background-color: var(--hover-bg);
    color: var(--hover-fg);
  }
  .insert {
    flex: 1 1 0;
    min-width: 0;
    display: flex;
    padding: 8px;
    border: none;
    background-color: transparent;
    color: inherit;
    text-align: start;
  }
  .actions {
    visibility: hidden;
  }
  .text-block:hover .actions,
  .text-block:focus-within .actions {
    visibility: visible;
  }
  .empty {
    padding: 8px;
    opacity: 70%;
  }
  .add {
    border-block-start: 1px solid var(--border);
    margin-block-start: 4px;
    padding-block-start: 4px;
  }
</style>
