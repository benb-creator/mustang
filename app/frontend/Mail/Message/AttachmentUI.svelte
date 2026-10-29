<Clickable onClick={onOpen} disabled={executable}>
  <hbox class="attachment"
    draggable="true"
    on:dragstart={onDragStart}
    title={executable}
    >
    <hbox bind:this={iconEl}>
      <hbox class="icon">
        <FileIcon ext={$attachment.ext} localFilePath={$attachment.filepathLocal} size={24} />
      </hbox>
      <vbox class="info">
        <hbox title={executable ?? $attachment.filename} class="filename top-row font-normal">
          {$attachment.filename}
        </hbox>
        <hbox class="bottom-row font-smallest">
          <hbox class="size">
            {$attachment.size ? fileSize($attachment.size) : $t`Not downloaded`}
          </hbox>
          <hbox flex />
          <AttachmentMenu {attachment} />
        </hbox>
      </vbox>
    </hbox>
  </hbox>
</Clickable>

<script lang="ts">
  import type { Attachment } from "../../../logic/Abstract/Attachment";
  import { fileSize } from "../../Files/file";
  import { openFileInternallyFromFile, canOpenFileInternally } from "../../Files/open";
  import { assert } from "../../../logic/util/util";
  import { executableMessage } from "../../../logic/Files/FileType/ExecutableFile";
  import AttachmentMenu from "./AttachmentMenu.svelte";
  import FileIcon from "../../Files/Thumbnail/FileIcon.svelte";
  import Clickable from "../../Shared/Clickable.svelte";
  import { t } from "../../../l10n/l10n";

  export let attachment: Attachment;

  /** Why we refuse to open it. null = safe. */
  $: executable = $attachment.executable ? executableMessage($attachment.executable) : null;

  async function onOpen() {
    if (canOpenFileInternally(attachment.mimeType)) {
      await attachment.load();
      await openFileInternallyFromFile(attachment.content);
    } else {
      if (!attachment.filepathLocal) {
        await attachment.load();
      }
      await attachment.openOSApp();
    }
  }

  let iconEl: HTMLDivElement;

  function onDragStart(event: DragEvent) {
    assert(attachment.content instanceof File, $t`Attachment file is missing`);
    event.dataTransfer.items.clear();
    event.dataTransfer.items.add(attachment.content);
    event.dataTransfer.setDragImage(iconEl as HTMLElement, 0, 0);
    event.dataTransfer.effectAllowed = "copy";
    for (let item of event.dataTransfer.items) {
      console.log("dragging attachment file", item, item.kind, item.type);
    }
    // TODO doesn't work for me: Creates a .txt file with the filename as content
  }
</script>

<style>
  .attachment {
    height: 40px;
    margin: 4px;
  }
  .icon {
    aspect-ratio: 1/1;
    background-color: var(--outstanding-bg);
    color: var(--outstanding-fg);
    align-items: center;
    justify-content: center;
    border-top-left-radius: 3px;
    border-bottom-left-radius: 3px;
  }
  .info {
    width: 160px;
    padding: 2px 8px 2px 8px;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
    background-color: var(--main-bg);
    color: var(--main-fg);
    box-shadow: 2px 0px 6px 0px rgba(0, 0, 0, 10%);
  }
  .attachment:hover .icon {
    background-color: var(--inverted-bg);
    color: var(--inverted-fg);
  }
  .top-row,
  .bottom-row,
  .size {
    align-items: center;
  }
  .filename,
  .size {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .top-row {
  }
  .bottom-row {
  }
  .bottom-row :global(.svelteui-Popper-root) {
    position: fixed;
  }
  :global(.fresh) .attachment {
    position: relative;
    box-sizing: border-box;
    height: 36px;
    margin: 0;
    border: 1px solid var(--border);
    border-radius: var(--radius-m);
    background-color: var(--l3-bg);
    overflow: hidden;
    cursor: pointer;
    transition: border-color var(--motion-fast) var(--motion-ease);
  }
  :global(.fresh) .attachment:hover {
    border-color: var(--fg-3);
  }
  :global(.fresh) .icon {
    width: 32px;
    aspect-ratio: auto;
    border-radius: 0;
    background-color: transparent;
    color: var(--fg-2);
  }
  :global(.fresh) .attachment:hover .icon {
    background-color: transparent;
    color: var(--accent-fg);
  }
  :global(.fresh) .info {
    justify-content: center;
    width: 168px;
    padding: 0 28px 0 0;
    border-radius: 0;
    background-color: transparent;
    color: var(--fg-1);
    box-shadow: none;
  }
  :global(.fresh) .filename {
    display: block;
    font-size: var(--text-m);
    line-height: 16px;
  }
  :global(.fresh) .bottom-row :global(.menu.button) {
    position: absolute;
    inset-inline-end: 4px;
    top: 50%;
    transform: translateY(-50%);
  }
  :global(.fresh) .bottom-row :global(.menu.button .button.button) {
    min-width: var(--icon-button-size-s);
    min-height: var(--icon-button-size-s);
    height: var(--icon-button-size-s);
  }
  :global(.fresh) .size {
    display: block;
    font-size: var(--text-s);
    line-height: 16px;
    color: var(--fg-2);
    font-variant-numeric: tabular-nums;
  }
</style>
