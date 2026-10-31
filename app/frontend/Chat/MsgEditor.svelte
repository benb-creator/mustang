<FileDropTarget
  on:add-files={onAddAttachment}>
  <!--on:inline-files={onAddInline}
  allowInline={true}>-->
  <vbox flex class="msg-editor">
    {#if showEmojis}
      <hbox>
        <vbox class="emojis">
          <GraphicSelector
            on:select={onEmoji}
            on:backspace={() => catchErrors(onEmojiBackspace)}
            bind:isOpen={showEmojis}
            />
        </vbox>
        <vbox class="emoji-empty" flex />
      </hbox>
    {/if}
    {#if $attachments.hasItems}
      <vbox class="attachments">
        <AttachmentsPane message={to.draftMessage} />
      </vbox>
    {/if}
    <hbox flex class="input-row">
      {#if appGlobal.isMobile}
        <hbox class="input-buttons">
          <Button classes="formatting-toggle"
            label={$t`Formatting`}
            onClick={() => showFormatting = !showFormatting}
            icon={FormattingIcon}
            iconSize="22px"
            iconOnly plain
            selected={showFormatting}
            />
          <Button classes="attach"
            label={$t`Add attachment`}
            onClick={onAttachFiles}
            icon={AttachIcon}
            iconSize="22px"
            iconOnly plain
            />
        </hbox>
        <FileSelector bind:this={fileSelector} />
      {/if}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <vbox flex class="editor-wrapper" on:keydown|capture={ev => isEnterSend && onKeyEnter(ev, () => catchErrors(send))}>
        {#if !appGlobal.isMobile || showFormatting}
          <HTMLEditorToolbar {editor}>
            <Button classes="emoji-toggle"
              onClick={() => showEmojis = !showEmojis}
              icon={EmojiIcon}
              iconSize="16px"
              selected={showEmojis}
              slot="start"
              />
            <Button classes="enter-toggle"
              onClick={() => isEnterSend = !isEnterSend}
              icon={EnterKeyIcon}
              iconSize="16px"
              selected={!isEnterSend}
              slot="last"
              />
          </HTMLEditorToolbar>
        {/if}
        <vbox flex class="editor-scroll-wrapper">
          <Scroll>
            <vbox flex class="editor">
              <HTMLEditor bind:html={to.draftMessage.rawHTMLDangerous} bind:editor />
            </vbox>
          </Scroll>
        </vbox>
      </vbox>
      <vbox class="send-buttons">
        <RoundButton classes="send-button"
          onClick={send}
          icon={SendIcon}
          iconSize="24px"
          padding="6px"
          border={false}
          disabled={!to.draftMessage.hasHTML && $attachments.isEmpty}
          />
      </vbox>
    </hbox>
  </vbox>
</FileDropTarget>

<script lang="ts">
  import type { ChatRoom } from "../../logic/Chat/ChatRoom";
  import { insertImage } from "../Shared/Editor/InsertImage";
  import { selectedDraft, selectedEditor } from "./selected";
  import HTMLEditorToolbar from "../Shared/Editor/HTMLEditorToolbar.svelte";
  import HTMLEditor from "../Shared/Editor/HTMLEditor.svelte";
  import FileDropTarget from "../Mail/Composer/Attachments/FileDropTarget.svelte";
  import FileSelector from "../Mail/Composer/Attachments/FileSelector.svelte";
  import AttachmentsPane from "../Mail/Composer/Attachments/AttachmentsPane.svelte";
  import GraphicSelector from "./Emoji/GraphicSelector.svelte";
  import Scroll from "../Shared/Scroll.svelte";
  import RoundButton from "../Shared/RoundButton.svelte";
  import Button from "../Shared/Button.svelte";
  import SendIcon from "lucide-svelte/icons/send";
  import EnterKeyIcon from "lucide-svelte/icons/corner-down-left";
  import EmojiIcon from "lucide-svelte/icons/smile";
  import FormattingIcon from "lucide-svelte/icons/type";
  import AttachIcon from "lucide-svelte/icons/paperclip";
  import { appGlobal } from "../../logic/app";
  import { onKeyEnter } from "../Util/util";
  import { catchErrors } from "../Util/error";
  import { assert } from "../../logic/util/util";
  import type { Editor } from '@tiptap/core';
  import { t } from "../../l10n/l10n";

  export let to: ChatRoom;

  let editor: Editor;

  let isEnterSend = !appGlobal.isMobile;
  $: to.draftMessage ??= to.newMessage();
  $: attachments = $to.draftMessage.attachments;
  $: $selectedDraft = $to.draftMessage;
  $: $selectedEditor = editor;
  let showEmojis = false;
  let showFormatting = false;

  async function send() {
    assert(to.draftMessage.hasHTML || to.draftMessage.attachments.hasItems, "Message is empty");
    let msg = to.draftMessage;
    msg.outgoing = true;
    msg.text; // Generate to keep in sync
    msg.contact = to.contact;
    msg.sent = new Date();
    await to.sendMessage(msg);
    reset();
  }

  function reset() {
    to.draftMessage = to.newMessage();
    editor.commands.setContent(""); // TODO fix HTMLEditor to listen to `html`
  }

  function onAddAttachment(event: CustomEvent) {
    addAttachments(event.detail.files as File[]);
  }

  let fileSelector: FileSelector;
  async function onAttachFiles() {
    let files = await fileSelector.selectFiles();
    if (!files?.length) {
      return;
    }
    addAttachments(files);
  }

  function addAttachments(files: File[]) {
    for (let file of files) {
      let att = to.draftMessage.newAttachment();
      att.fromFile(file);
      attachments.add(att);
    }
  }

  async function onAddInline(event: CustomEvent) {
    let files = event.detail.files as File[];
    for (let file of files) {
      await insertImage(editor, file, to.draftMessage); // sequential, to keep the image order
    }
  }

  function onEmoji(ev: CustomEvent) {
    let emoji = ev.detail.emoji;
    if (emoji) {
      editor.commands.insertContent(emoji);
    }
  }

  function onEmojiBackspace() {
    editor.view.focus();
    document.execCommand("delete");
  }
</script>

<style>
  .msg-editor {
    background-color: var(--leftbar-bg);
    color: var(--leftbar-fg);
    padding: 4px 4px 10px 10px;
  }
  .emojis {
    height: 300px;
    width: 600px;
  }
  .attachments {
    height: 112px;
  }
  .attachments :global(.attachments-pane .inside) {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: start;
  }
  .attachments :global(.attachments-pane .attachment) {
    min-width: 200px;
  }
  .attachments :global(.attachments-pane .buttons) {
    margin-inline-start: 12px;
  }
  .editor-wrapper {
    flex: 3 0 0;
    height: 112px;
  }
  .editor-scroll-wrapper {
    background-color: var(--main-bg);
    color: var(--main-bf);
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .editor {
    font-family: unset;
    padding: 8px 12px;
  }
  .send-buttons {
    align-self: flex-end;
    margin-inline-start: 2px;
    margin-block-end: 2px;
  }
  .send-buttons :global(.button) {
    background-color: unset;
  }
  :global(.mobile) .msg-editor {
    padding: 6px 4px 6px 4px;
  }
  :global(.mobile) .input-row {
    align-items: end;
  }
  :global(.mobile) .input-buttons :global(button) {
    width: 44px;
    height: 44px;
  }
  :global(.mobile) .editor-wrapper {
    height: auto;
    min-width: 0px;
    gap: 4px;
  }
  :global(.mobile) .editor-wrapper :global(.toolbar) {
    flex-wrap: nowrap;
    overflow-x: auto;
    scrollbar-width: none;
    contain: inline-size;
  }
  :global(.mobile) .editor-wrapper :global(.toolbar button.button) {
    flex-shrink: 0;
    min-width: 44px;
    min-height: 44px;
  }
  :global(.mobile) .editor-scroll-wrapper {
    border-radius: 22px;
  }
  :global(.mobile) .editor-scroll-wrapper :global(.scroll) {
    flex: none;
    max-height: 9.5em;
  }
  :global(.mobile) .editor-scroll-wrapper :global(.inside) {
    position: static;
    height: auto;
  }
  :global(.mobile) .editor {
    flex: none;
    min-height: 42px;
    font-size: 16px;
    justify-content: center;
    padding: 8px 14px;
  }
  :global(.mobile) .send-buttons {
    margin: 0px;
  }
  :global(.mobile) .send-buttons :global(button) {
    width: 44px;
    height: 44px;
  }
  :global(.mobile) .emojis {
    width: 100%;
    height: 260px;
    contain: inline-size;
  }
  :global(.mobile) .emoji-empty {
    display: none;
  }
</style>
