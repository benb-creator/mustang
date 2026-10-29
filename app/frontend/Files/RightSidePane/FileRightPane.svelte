<vbox class="right-side-bar" flex>
  <vbox class="preview">
    {#if $viewFile}
      <vbox class="thin-right-side-bar" flex>
        <RoundButton
          onClick={onClosePreview}
          label={$t`Close file`}
          icon={XIcon}
          iconSize="18px"
          padding="4px"
          classes="plain"
          />
        <RoundButton
          onClick={() => $isRightSidebarExpanded = false}
          label={$t`Collapse sidebar`}
          icon={CollapseIcon}
          iconSize="18px"
          padding="4px"
          classes="plain"
          />
      </vbox>
    {:else if canPreview}
      <Clickable onDoubleClick={() => openPreview(file)}>
        <Thumbnail {file} size={200} preview />
      </Clickable>
      <hbox class="open-preview buttons">
        <RoundButton
          onClick={() => openPreview(file)}
          icon={OpenPreviewIcon}
          />
      </hbox>
    {/if}
  </vbox>
  <vbox class="content" flex>
    <hbox class="open buttons">
      <Button
        onClick={() => file.openOSApp()}
        label={$t`Open`}
        label-should={$t`Open with ${"PhotoShop"}`}
        tooltip={$t`Open with a local application on your computer`}
        >
        <FileIcon ext={$file.ext} localFilePath={$file.path} size={20} slot="icon" />
      </Button>
      <RoundButton
        onClick={() => openFileInCloudApp(file)}
        icon={OpenCloudIcon}
        label={$t`Open with a cloud app on the web`}
        disabled={cloudAppDisabledReason}
        iconSize="20px"
        padding="6px"
        classes="secondary"
        />
    </hbox>

    <ErrorMessageInline bind:this={error} />

    <Rename {file} />

    <hbox class="file-properties font-small">
      <hbox class="lastMod">{getDateTimeString($file.lastMod)}</hbox>
      <hbox flex />
      <hbox class="size">{fileSize($file.size)}</hbox>
    </hbox>

    <ActionToolbar {file} />
  </vbox>
</vbox>

<script lang="ts">
  import type { File } from "../../../logic/Files/File";
  import { canShowPreview, fileSize, openFileInCloudApp, openPreview } from "../file";
  import { isRightSidebarExpanded, viewFile, fileViewer } from "../selected";
  import type { WebAppListed } from "../../../logic/WebApps/WebAppListed";
  import Rename from "./Rename.svelte";
  import ActionToolbar from "./ActionToolbar.svelte";
  import Thumbnail from "../Thumbnail/Thumbnail.svelte";
  import FileIcon from "../Thumbnail/FileIcon.svelte";
  import ErrorMessageInline from "../../Shared/ErrorMessageInline.svelte";
  import Button from "../../Shared/Button.svelte";
  import RoundButton from "../../Shared/RoundButton.svelte";
  import OpenPreviewIcon from "lucide-svelte/icons/expand";
  import OpenCloudIcon from "lucide-svelte/icons/cloud";
  import CollapseIcon from "lucide-svelte/icons/chevrons-right";
  import XIcon from "lucide-svelte/icons/x";
  import { getDateTimeString } from "../../../logic/util/date";
  import { catchErrors } from "../../Util/error";
  import { t } from "../../../l10n/l10n";
  import type { Collection } from "svelte-collections";
  import Clickable from "../../Shared/Clickable.svelte";

  export let file: File;

  let error: ErrorMessageInline;

  $: canPreview = canShowPreview(file);
  let editors: Collection<WebAppListed>;
  $: error && file && catchErrors(async () => editors = await file.availableOnlineEditors(), error.showError);
  $: error && canPreview && catchErrors(async () => canPreview && await file.getURL(), error.showError);
  $: cloudAppDisabledReason = editors?.hasItems ? null
    : file.account
      ? $t`${file.account.name} does not offer a cloud app for this file type`
      : $t`No cloud app is available for this file`; // EMail attachments can't be opened in cloud apps

  function onClosePreview() {
    $viewFile = null;
    $fileViewer = null;
  }
</script>

<style>
  .right-side-bar {
    box-shadow: -2px 0px 3px 1px #e3e3e3;
  }
  .thin-right-side-bar {
    align-items: end;
    padding: 8px 4px;
    gap: 8px;
  }
  .content {
    align-items: stretch;
    padding-block: 8px;
    padding-inline: 20px;
  }
  .preview {
    height: 200px;
    width: 100%;
    position: relative;
    /*background-image: url("../../asset/header-background.jpeg");*/
  }
  .open-preview {
    position: absolute;
    top: 0px;
    right: 0px;
  }
  .file-properties {
    opacity: 60%;
  }
  .buttons {
    align-items: start;
    gap: 8px;
    margin: 6px 8px 6px 0px;
  }
  .open.buttons {
    margin-block-end: 16px;
  }
  .open.buttons :global(button.disabled svg path) {
    stroke-width: 1px;
  }
  :global(.fresh) .right-side-bar {
    box-shadow: none;
    min-height: 0;
    overflow-y: auto;
  }
  :global(.fresh) .preview {
    flex: none;
    box-sizing: border-box;
    width: auto;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    margin: 16px 16px 0;
    border-radius: var(--radius-m);
    background-color: var(--l2-bg);
    color: var(--fg-3);
  }
  :global(.fresh) .preview:has(.thin-right-side-bar) {
    align-items: stretch;
    margin: 0;
    border-radius: 0;
    background-color: transparent;
  }
  :global(.fresh) .preview > :global(div > img) {
    max-width: 100%;
    max-height: 100%;
  }
  :global(.fresh) .preview > :global(div > svg) {
    width: 96px;
    height: 96px;
    stroke-width: 1px;
  }
  :global(.fresh) .open-preview {
    top: 8px;
    right: 8px;
    margin: 0;
  }
  :global(.fresh) .thin-right-side-bar {
    flex-direction: row;
    justify-content: end;
    padding: 8px;
    gap: 4px;
  }
  :global(.fresh) .content {
    gap: 12px;
    padding: 16px;
  }
  :global(.fresh) .buttons {
    align-items: center;
    gap: 8px;
    margin: 0;
  }
  :global(.fresh) .open.buttons {
    margin-block-end: 0;
  }
  :global(.fresh) .file-properties {
    gap: 12px;
    opacity: 1;
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-variant-numeric: tabular-nums;
    color: var(--fg-2);
  }
</style>
