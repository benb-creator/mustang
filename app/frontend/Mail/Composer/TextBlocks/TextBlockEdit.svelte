<!-- svelte-ignore a11y_no_static_element_interactions -->
<vbox class="text-block-edit" on:keydown={onKeyEscape}>
  <hbox class="title">{isNew ? $t`New text block` : $t`Edit text block`}</hbox>
  <vbox class="text">
    <HTMLEditor bind:html bind:editor extraExtensions={[PlaceholderHighlight]} />
  </vbox>
  <vbox class="placeholders">
    <hbox class="label font-small">{$t`Replace the selected text with`}</hbox>
    <hbox class="placeholder-buttons">
      {#each TextBlockPlaceholder.all as placeholder}
        <Button
          label={placeholder.label}
          tooltip={placeholder.code}
          onClick={() => onInsertPlaceholder(placeholder)}
          classes="placeholder font-small"
          />
      {/each}
    </hbox>
  </vbox>
  <hbox class="keyword">
    <label for="text-block-keyword">{$t`Keyword`}</label>
    <hbox class="prefix">::</hbox>
    <input type="text" id="text-block-keyword"
      bind:value={keyword}
      bind:this={keywordInput}
      on:keydown={event => onKeyEnter(event, onSave)}
      />
  </hbox>
  <hbox class="hint font-small" class:error={!!keywordError}>
    {keywordError ?? $t`Type ::${shownKeyword} in the email to insert this text block`}
  </hbox>
  <hbox class="buttons">
    <Button
      label={$t`Cancel`}
      onClick={onCancel}
      />
    <Button
      label={isNew ? $t`Add` : $t`Save`}
      onClick={onSave}
      disabled={saveDisabled}
      classes="filled"
      />
  </hbox>
</vbox>

<script lang="ts">
  import type { TextBlock } from "../../../../logic/Mail/TextBlock/TextBlock";
  import { TextBlockPlaceholder } from "../../../../logic/Mail/TextBlock/TextBlockPlaceholder";
  import { textBlocks } from "../../../../logic/Mail/TextBlock/TextBlocks";
  import { PlaceholderHighlight } from "./PlaceholderHighlight";
  import HTMLEditor from "../../../Shared/Editor/HTMLEditor.svelte";
  import Button from "../../../Shared/Button.svelte";
  import { onKeyEnter } from "../../../Util/util";
  import { t } from "../../../../l10n/l10n";
  import type { Editor } from "@tiptap/core";
  import { createEventDispatcher, onMount, tick } from "svelte";
  const dispatchEvent = createEventDispatcher<{ save: TextBlock, cancel: void }>();

  /** New or existing. Changed only when the user saves. */
  export let block: TextBlock;

  let isNew = !textBlocks.contains(block);
  let html = block.html ?? "";
  let keyword = block.keyword ?? "";
  let editor: Editor;
  let keywordInput: HTMLInputElement;

  onMount(async () => {
    await tick();
    if (editor?.isEmpty) {
      editor.commands.focus("end");
    } else {
      keywordInput.focus();
    }
  });

  $: cleanKeyword = keyword.trim().replace(/^:+/, "");
  $: shownKeyword = cleanKeyword || $t`keyword`;
  $: keywordError =
    /\s/.test(cleanKeyword) ? $t`The keyword must not contain spaces` :
    textBlocks.find(existing => existing != block && existing.matchesKeyword(cleanKeyword)) ? $t`There is already a text block with the keyword ${cleanKeyword}` :
    null;
  $: saveDisabled =
    !cleanKeyword ? $t`Please enter a keyword` :
    !editor || editor.isEmpty ? $t`Please enter the text` :
    keywordError ?? false;

  function onInsertPlaceholder(placeholder: TextBlockPlaceholder) {
    editor.chain().focus().insertContent(placeholder.code).run();
  }

  async function onSave() {
    if (saveDisabled) {
      return;
    }
    block.keyword = cleanKeyword;
    block.html = editor.getHTML();
    if (!textBlocks.contains(block)) {
      textBlocks.add(block);
    }
    await textBlocks.save();
    dispatchEvent("save", block);
  }

  function onCancel() {
    dispatchEvent("cancel");
  }

  function onKeyEscape(event: KeyboardEvent) {
    if (event.key != "Escape") {
      return;
    }
    event.stopPropagation();
    onCancel();
  }
</script>

<style>
  .text-block-edit {
    width: 32em;
    max-width: 90vw;
    gap: 12px;
  }
  .title {
    font-weight: bold;
  }
  .text {
    min-height: 5em;
    max-height: 15em;
    overflow-y: auto;
    padding: 1em 12px;
    border: 1px solid var(--input-line);
    border-radius: var(--border-radius);
    background-color: var(--input-bg);
    color: var(--input-fg);
  }
  .text:focus-within {
    border-color: var(--input-focus);
  }
  .text :global(.text-block-placeholder) {
    background-color: var(--offset-bg);
    color: var(--offset-fg);
    border-radius: 3px;
    padding: 0 2px;
  }
  .placeholders {
    gap: 4px;
  }
  .placeholder-buttons {
    flex-wrap: wrap;
    gap: 4px;
  }
  .placeholder-buttons :global(button.placeholder) {
    padding: 2px 8px;
  }
  .keyword {
    align-items: baseline;
  }
  .keyword label {
    margin-inline-end: 8px;
  }
  .keyword input {
    flex: 1 1 0;
  }
  .prefix {
    opacity: 60%;
    margin-inline-end: 2px;
  }
  .hint {
    opacity: 70%;
    margin-block-start: -8px;
  }
  .hint.error {
    opacity: 100%;
    color: red;
  }
  .buttons {
    justify-content: end;
    gap: 8px;
  }
</style>
