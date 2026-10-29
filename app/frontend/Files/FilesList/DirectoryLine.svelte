<Clickable onClick={toggleOpen}>
  <hbox class="directory line"
    class:selected={dir == $selectedFile}
    on:drop={event => catchErrors(() => onDropFile(event, dir))}
    on:dragover={event => catchErrors(() => onDragOverFile(event, dir))}>
    <hbox class="firstColumn">
      {#each {length: indent} as _}
        <hbox class="indention" />
      {/each}
      <button class="icon">
        {#if open}
          📂
        {:else}
          📁
        {/if}
      </button>
      <hbox class="name">
        {$dir?.name}
      </hbox>
    </hbox>
    <hbox class="type">
      {$t`Folder`}
    </hbox>
    <hbox class="size">
      {#if $subDirs.hasItems || $files.hasItems}
        {$t`${$subDirs?.length + $files?.length} entries`}
      {/if}
    </hbox>
    <hbox class="time">
      {$dir?.lastMod ? getDateTimeString($dir.lastMod) : ""}
    </hbox>
  </hbox>
</Clickable>

{#if open}
  <FileOrDirLines {files} dirs={subDirs} indent={indent + 1} />
{/if}

<script lang="ts">
  import { Directory } from "../../../logic/Files/Directory";
  import { selectedFile } from "../selected";
  import { onDropFile, onDragOverFile } from "../drag";
  import { getDateTimeString } from "../../../logic/util/date";
  import FileOrDirLines from "./FileOrDirLines.svelte";
  import Clickable from "../../Shared/Clickable.svelte";
  import FolderClosedIcon from "lucide-svelte/icons/folder";
  import FolderOpenIcon from "lucide-svelte/icons/folder-open";
  import { catchErrors } from "../../Util/error";
  import { t } from "../../../l10n/l10n";

  export let dir: Directory;
  export let indent = 0;

  let open = false;
  $: subDirs = dir?.subDirs;
  $: files = dir?.files;

  function toggleOpen() {
    open = !open;
    if (open) {
      dir.listContents()
        .catch(console.error);
    }
  }
  /*async function listContents(dir: Directory) {
    await dir.listContents();
    await Promise.all(dir.subDirs.contents.map(subDir =>
      subDir.listContents)); // TODO doesn't update the UI
  }*/
</script>

<style>
  .line {
    display: contents;
  }
  .line:hover:not(.selected) > * {
    background-color: var(--hover-bg);
    color: var(--hover-fg);
  }
  .line.selected > * {
    background-color: var(--selected-bg);
    color: var(--selected-fg);
  }
  .name, .type, .size, .time {
    padding-inline-start: 8px;
    padding-inline-end: 8px;
  }
  .icon {
    padding-inline-start: 16px;
    padding-inline-end: 0px;
    margin-block-start: 2px;
  }
  .icon :global(svg) {
    stroke-width: 1.5px;
  }
  .time {
    padding-inline-end: 16px;
  }
  .icon {
    align-self: center;
    border: none;
    background-color: transparent;
  }
  .indention {
    margin-inline-start: 16px;
  }
  .type {
    min-width: 3.5em;
  }
  .size {
    justify-content: end;
    min-width: 8em;
  }
  .time {
    justify-content: end;
    min-width: 5em;
  }
  .type, .size, .time {
    color: #91939D;
    font-size: 90%;
    font-weight: 300;
  }
  :global(.fresh) .line > * {
    box-sizing: border-box;
    min-height: var(--file-row-height);
    align-items: center;
  }
  :global(.fresh) .line:hover:not(.selected) > * {
    background-color: var(--row-hover);
    color: inherit;
  }
  :global(.fresh) .line.selected > * {
    background-color: var(--sel-bg);
    color: var(--sel-fg);
  }
  :global(.fresh) .firstColumn {
    min-width: 0;
  }
  :global(.fresh) .icon {
    flex: none;
    align-items: center;
    justify-content: center;
    width: 16px;
    margin-block-start: 0;
    margin-inline-end: 4px;
    padding: 0;
    margin-inline-start: 16px;
    color: var(--fg-2);
  }
  :global(.fresh) .name {
    display: block;
    min-width: 0;
    font-size: var(--text-m);
    line-height: var(--line-m);
    color: var(--fg-1);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  :global(.fresh) .type,
  :global(.fresh) .size,
  :global(.fresh) .time {
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-weight: 400;
    font-variant-numeric: tabular-nums;
    color: var(--fg-2);
    white-space: nowrap;
  }
  :global(.fresh) .line.selected .name {
    color: var(--sel-fg);
  }
  :global(.fresh) .line.selected .icon,
  :global(.fresh) .line.selected .type,
  :global(.fresh) .line.selected .size,
  :global(.fresh) .line.selected .time {
    color: var(--sel-fg-2);
  }
  :global(.fresh) .directory .icon {
    font-size: 14px;
    line-height: 16px;
    color: transparent;
    text-shadow: 0 0 0 var(--accent-fg);
  }
  :global(.fresh) .directory.selected .icon {
    color: transparent;
    text-shadow: 0 0 0 var(--sel-fg);
  }
</style>
