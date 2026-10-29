<!-- One attachment in a chat message: images render inline; everything else
  shows as a file chip you can open or drag out. The bytes arrive via a background
  download (WhatsApp/XMPP) or are already present (our own outgoing message), and
  `Attachment` is observable, so this updates when `content`/`size` fill in. -->
{#if isImage}
  <vbox class="image-wrap">
    {#if $attachment.content}
      <Clickable onClick={onOpen}>
        <img class="image" src={$attachment.blobURL} alt={$attachment.filename} />
      </Clickable>
      <hbox class="image-menu">
        <AttachmentMenu {attachment} />
      </hbox>
    {:else}
      <hbox class="loading font-smallest">
        {#await attachment.read()}
          {$t`Loading…`}
        {:then}
          <!-- Still no content, so file is not on disk. We assume the protocol downloads it in the background. -->
          {$t`Downloading…`}
        {:catch ex}
          <ErrorMessageInline {ex} />
        {/await}
      </hbox>
    {/if}
  </vbox>
{:else}
  <Clickable onClick={onOpen}>
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <hbox class="file" draggable="true" on:dragstart={onDragStart}>
      <hbox class="icon">
        <FileIcon ext={$attachment.ext} localFilePath={$attachment.filepathLocal} size={24} />
      </hbox>
      <vbox class="info">
        <hbox class="filename top-row font-normal" title={$attachment.filename}>
          {$attachment.filename}
        </hbox>
        <hbox class="bottom-row font-smallest">
          <hbox class="size">
            {#if $attachment.size}
              {fileSize($attachment.size)}
            {:else}
              {$t`Downloading…`}
            {/if}
          </hbox>
          <hbox flex />
          <AttachmentMenu {attachment} />
        </hbox>
      </vbox>
    </hbox>
  </Clickable>
{/if}

<script lang="ts">
  import type { Attachment } from "../../../logic/Abstract/Attachment";
  import { fileSize } from "../../Files/file";
  import { openFileInternallyFromFile, canOpenFileInternally } from "../../Files/open";
  import { saveBlobAsFile } from "../../Util/util";
  import AttachmentMenu from "../../Mail/Message/AttachmentMenu.svelte";
  import FileIcon from "../../Files/Thumbnail/FileIcon.svelte";
  import Clickable from "../../Shared/Clickable.svelte";
  import ErrorMessageInline from "../../Shared/ErrorMessageInline.svelte";
  import { t } from "../../../l10n/l10n";

  export let attachment: Attachment;

  $: isImage = $attachment.mimeType?.startsWith("image/");

  async function onOpen() {
    if (!attachment.content) {
      await attachment.read(); // restore the bytes from disk if we have them
    }
    let content = await attachment.getContent();
    if (!content) {
      return; // not downloaded yet
    }
    if (canOpenFileInternally(attachment.mimeType)) {
      await openFileInternallyFromFile(content);
    } else {
      await saveBlobAsFile(content); // offer to save the blob to disk
    }
  }

  function onDragStart(event: DragEvent) {
    if (!(attachment.content instanceof File)) {
      return;
    }
    event.dataTransfer.items.clear();
    event.dataTransfer.items.add(attachment.content);
    event.dataTransfer.effectAllowed = "copy";
  }
</script>

<style>
  :global(.bubble) :has(.image) {
    background-color: blue;
    padding: 20px;
  }
  :global(.bubble:before) :has(.image) {
    display: none;
  }
  .image-wrap {
    position: relative;
  }
  /* The attachment menu, over the image's top-right corner; appears on hover. */
  .image-menu {
    position: absolute;
    top: 2px;
    inset-inline-end: 2px;
    padding: 0 2px;
    border-radius: 4px;
    background-color: rgba(255, 255, 255, 80%);
    opacity: 0;
  }
  .image-wrap:hover .image-menu {
    opacity: 1;
  }
  .image {
    max-width: 280px;
    max-height: 320px;
    border-radius: 3px;
    object-fit: contain;
    cursor: pointer;
    margin: -8px -14px;
  }
  .loading {
    padding: 24px;
    color: #888888;
  }
  .file {
    height: 40px;
    cursor: pointer;
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
    padding: 2px 8px;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
    background-color: var(--main-bg);
    color: var(--main-fg);
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
  .bottom-row :global(.svelteui-Popper-root) {
    position: fixed;
  }
  :global(.fresh) .image-menu {
    border: 1px solid var(--border-float);
    border-radius: var(--radius-m);
    background-color: var(--float-bg);
  }
  :global(.fresh) .image {
    margin: 0;
    border-radius: var(--radius-l);
  }
  :global(.fresh) .loading {
    padding: 16px;
    color: var(--fg-3);
  }
  :global(.fresh) .file {
    height: 44px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-m);
    overflow: hidden;
    background-color: var(--l3-bg);
  }
  :global(.fresh) .icon {
    width: 44px;
    border-radius: 0;
    background-color: var(--fill-subtle);
    color: var(--fg-2);
  }
  :global(.fresh) .info {
    justify-content: center;
    width: 180px;
    padding: 2px 6px 2px 10px;
    border-radius: 0;
    background-color: transparent;
    color: var(--fg-1);
  }
  :global(.fresh) .filename {
    font-size: var(--text-m);
    line-height: var(--line-m);
  }
  :global(.fresh) .bottom-row {
    font-size: var(--text-s);
    color: var(--fg-2);
  }
</style>
