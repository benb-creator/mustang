<!-- Mimics `MailComposer`: the email editor with the text blocks button
  in its toolbar, and the list that typing `::keyword` opens -->
<vbox class="mail-composer-window">
  <HTMLEditorToolbar {editor}>
    <Button
      label="Text blocks"
      shortCutInfo="::keyword"
      iconOnly
      onClick={() => showTextBlocks = !showTextBlocks}
      bind:buttonEl={textBlocksAnchor}
      slot="end"
      />
  </HTMLEditorToolbar>
  <HTMLEditor bind:html bind:editor {extraExtensions} />
  <TextBlockSuggestions {editor} />
</vbox>
<Popup
  bind:popupOpen={showTextBlocks}
  popupAnchor={textBlocksAnchor}
  boundaryElSel=".mail-composer-window"
  placement="bottom-end"
  autoClose>
  <TextBlocksPopup {editor} on:close={() => showTextBlocks = false} />
</Popup>

<script lang="ts">
  import type { EMail } from "../../../../logic/Mail/EMail";
  import { TextBlockShortcut } from "../../../../frontend/Mail/Composer/TextBlocks/TextBlockShortcut";
  import TextBlocksPopup from "../../../../frontend/Mail/Composer/TextBlocks/TextBlocksPopup.svelte";
  import TextBlockSuggestions from "../../../../frontend/Mail/Composer/TextBlocks/TextBlockSuggestions.svelte";
  import HTMLEditor from "../../../../frontend/Shared/Editor/HTMLEditor.svelte";
  import HTMLEditorToolbar from "../../../../frontend/Shared/Editor/HTMLEditorToolbar.svelte";
  import Popup from "../../../../frontend/Shared/Popup.svelte";
  import Button from "../../../../frontend/Shared/Button.svelte";
  import type { Editor } from "@tiptap/core";

  export let mail: EMail;
  export let html: string;

  let editor: Editor;
  let extraExtensions = [
    TextBlockShortcut.configure({ getMail: () => mail }),
  ];
  let showTextBlocks = false;
  let textBlocksAnchor: HTMLButtonElement;

  export function getEditor(): Editor {
    return editor;
  }
</script>
