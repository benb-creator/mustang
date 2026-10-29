<Clickable onClick={onSelect} onDoubleClick={() => openFileInDefaultApp(file)}>
  <vbox class="file box"
    class:selected={file == $selectedFile}
    draggable="true"
    on:dragstart={event => catchErrors(() => onDragStartFile(event, file))}>
    <vbox class="tile">
      <button class="icon">
        <Thumbnail {file} size={48} preview />
      </button>
    </vbox>
    <vbox class="info">
      <hbox class="name">
        {$file?.name}
      </hbox>
      <hbox class="second">
        <hbox flex />
        <hbox class="time font-smallest">
          {$file?.lastMod ? getDateTimeString($file.lastMod) : ""}
        </hbox>
      </hbox>
    </vbox>
  </vbox>
</Clickable>

<script lang="ts">
  import { File } from "../../../logic/Files/File";
  import { canShowPreview, openFileInDefaultApp } from "../file";
  import { selectedFile } from "../selected";
  import { onDragStartFile } from "../drag";
  import Clickable from "../../Shared/Clickable.svelte";
  import Thumbnail from "../Thumbnail/Thumbnail.svelte";
  import { getDateTimeString } from "../../../logic/util/date";
  import { catchErrors } from "../../Util/error";

  export let file: File;

  $: catchErrors(async () => canShowPreview(file) && file.getURL(), console.error);

  function onSelect() {
    $selectedFile = file;
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
    border: none;
    background-color: transparent;
    padding-inline: 0px;
    margin-block-start: 2px;
    overflow: hidden;
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
    overflow-wrap: anywhere;
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
</style>
