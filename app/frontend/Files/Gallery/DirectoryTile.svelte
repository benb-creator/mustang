<Clickable onClick={toggleOpen}>
  <vbox class="directory box"
    class:selected={dir == $selectedFile}
    on:drop={event => catchErrors(() => onDropFile(event, dir))}
    on:dragover={event => catchErrors(() => onDragOverFile(event, dir))}>
    <vbox class="tile">
      <button class="icon">
        {#if open}
          📁
          <!--📂-->
        {:else}
          📁
        {/if}
      </button>
    </vbox>
    <vbox class="info">
      <hbox class="name">
        {$dir?.name}
      </hbox>
      <hbox class="second">
        <hbox flex />
        <hbox class="time font-smallest">
          {$dir?.lastMod ? getDateTimeString($dir.lastMod) : ""}
        </hbox>
      </hbox>
    </vbox>
  </vbox>

</Clickable>

<script lang="ts">
  import { Directory } from "../../../logic/Files/Directory";
  import { selectedFolder, selectedFile } from "../selected";
  import { onDropFile, onDragOverFile } from "../drag";
  import Clickable from "../../Shared/Clickable.svelte";
  import FolderClosedIcon from "lucide-svelte/icons/folder";
  import FolderOpenIcon from "lucide-svelte/icons/folder-open";
  import { getDateTimeString } from "../../../logic/util/date";
  import { catchErrors } from "../../Util/error";

  export let dir: Directory;

  function toggleOpen() {
    $selectedFolder = dir;
    dir.listContents()
      .catch(console.error);
  }
</script>

<style>
  .box:hover {
    background-color: var(--hover-bg);
    color: var(--hover-fg);
  }
  .tile {
    align-items: center;
    justify-content: center;
    width: 192px;
    height: 144px;
  }
  .icon {
    align-self: center;
    opacity: 60%;
    border: none;
    font-size: 5vw;
    background-color: transparent;
    padding-inline-start: 16px;
    padding-inline-end: 0px;
    margin-block-start: 2px;
  }
  .icon :global(svg) {
    stroke-width: 1.5px;
  }
  .info {
    max-width: 176px;
    padding-block: 4px;
    padding-inline: 8px;
  }
  .name, .second {
    max-height: 20px;
    overflow: hidden;
  }
  .time {
    padding-inline-end: 16px;
    justify-content: end;
    min-width: 5em;
    opacity: 50%;
    font-weight: 300;
  }
  :global(.fresh) .box {
    box-sizing: border-box;
    width: 148px;
    gap: 6px;
    padding: 8px;
    border-radius: var(--radius-m);
  }
  :global(.fresh) .box:hover {
    background-color: var(--row-hover);
    color: inherit;
  }
  :global(.fresh) .tile {
    box-sizing: border-box;
    width: 132px;
    height: 132px;
    overflow: hidden;
    border-radius: var(--radius-m);
    background-color: var(--l2-bg);
    color: var(--fg-2);
  }
  :global(.fresh) .box.selected .tile {
    box-shadow: 0 0 0 2px var(--accent);
  }
  :global(.fresh) .icon {
    margin: 0;
    padding: 0;
    color: inherit;
  }
  :global(.fresh) .info {
    max-width: 132px;
    padding: 0;
  }
  :global(.fresh) .name {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    max-height: calc(2 * var(--line-s));
    font-size: var(--text-s);
    line-height: var(--line-s);
    color: var(--fg-1);
    overflow: hidden;
    overflow-wrap: anywhere;
  }
  :global(.fresh) .second {
    max-height: var(--line-xs);
  }
  :global(.fresh) .time {
    min-width: 0;
    padding: 0;
    opacity: 1;
    font-size: var(--text-xs);
    line-height: var(--line-xs);
    font-weight: 400;
    font-variant-numeric: tabular-nums;
    color: var(--fg-3);
  }
  :global(.fresh) .directory .icon {
    opacity: 1;
    font-size: 56px;
    line-height: 64px;
    color: transparent;
    text-shadow: 0 0 0 var(--accent-fg);
  }
</style>
