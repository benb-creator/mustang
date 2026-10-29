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
    <hbox flex>
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <vbox flex class="editor-wrapper" on:keydown|capture={ev => isEnterSend && onKeyEnter(ev, () => catchErrors(send))}>
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
  import AttachmentsPane from "../Mail/Composer/Attachments/AttachmentsPane.svelte";
  import GraphicSelector from "./Emoji/GraphicSelector.svelte";
  import Scroll from "../Shared/Scroll.svelte";
  import RoundButton from "../Shared/RoundButton.svelte";
  import Button from "../Shared/Button.svelte";
  import SendIcon from "lucide-svelte/icons/send";
  import EnterKeyIcon from "lucide-svelte/icons/corner-down-left";
  import EmojiIcon from "lucide-svelte/icons/smile";
  import { onKeyEnter } from "../Util/util";
  import { catchErrors } from "../Util/error";
  import { assert } from "../../logic/util/util";
  import type { Editor } from '@tiptap/core';

  export let to: ChatRoom;

  let editor: Editor;

  let isEnterSend = true;
  $: to.draftMessage ??= to.newMessage();
  $: attachments = $to.draftMessage.attachments;
  $: $selectedDraft = $to.draftMessage;
  $: $selectedEditor = editor;
  let showEmojis = false;

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
    let files = event.detail.files as File[];
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

  :global(.fresh) .msg-editor {
    gap: 4px;
    padding: 8px 24px 12px;
    border-block-start: 1px solid var(--border);
    background-color: var(--l3-bg);
    color: var(--l3-fg);
  }
  :global(.fresh) .emojis {
    max-width: 100%;
    border: 1px solid var(--border-float);
    border-radius: var(--radius-l);
    background-color: var(--float-bg);
    box-shadow: var(--shadow-pop);
    overflow: hidden;
  }
  :global(.fresh) .editor-wrapper {
    gap: 4px;
  }
  :global(.fresh) .editor-scroll-wrapper {
    border: 1px solid var(--border-input);
    border-radius: var(--radius-m);
    background-color: var(--input-bg);
    color: var(--fg-1);
  }
  :global(.fresh) .editor-scroll-wrapper:hover {
    border-color: var(--fg-3);
  }
  :global(.fresh) .editor-scroll-wrapper:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }
  :global(.fresh) .editor {
    padding: 6px 10px;
    font-family: inherit;
    font-size: var(--text-l);
    line-height: var(--line-l);
  }
  :global(.fresh) .send-buttons {
    margin-inline-start: 8px;
    margin-block-end: 0;
  }
  :global(.fresh) .send-buttons :global(.button.button) {
    min-width: var(--control-height-l);
    min-height: var(--control-height-l);
  }
  :global(.fresh) .send-buttons :global(.button.button:not(.disabled)) {
    border-color: var(--accent);
    background-color: var(--accent);
    color: var(--fg-on-accent);
  }
  :global(.fresh) .send-buttons :global(.button.button:hover:not(.disabled)) {
    border-color: var(--accent-hover);
    background-color: var(--accent-hover);
    background-image: none;
    color: var(--fg-on-accent);
  }
  :global(.fresh) .send-buttons :global(.button.button.disabled) {
    background-color: var(--fill-subtle);
  }
  :global(.fresh) .send-buttons :global(svg) {
    width: 18px;
    height: 18px;
  }
</style>
