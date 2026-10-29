<NavRow
  label={$folder.name}
  icon={FolderIcon}
  {indent}
  expandable={$children.hasItems}
  {expanded}
  expanderToggles={false}
  {selected}
  nextLevel="l3"
  dropTarget={isDragOver}
  on:contextmenu={event => contextMenu.onContextMenu(event)}
  on:dragenter={onDragEnter}
  on:dragleave={onDragLeave}
  on:dragover={(event) => catchErrors(() => onDragOverFile(event, folder))}
  on:drop={(event) => catchErrors(() => onDrop(event))}
  />

<ContextMenu bind:this={contextMenu}>
  <FolderMenu {folder} />
</ContextMenu>

<script lang="ts">
  import type { Directory } from "../../../logic/Files/Directory";
  import { onDropFile, onDragOverFile } from "../../../frontend/Files/drag";
  import FolderMenu from "../../../frontend/Files/FolderLeftPane/FolderMenu.svelte";
  import ContextMenu from "../../../frontend/Shared/Menu/ContextMenu.svelte";
  import NavRow from "../../Shared/NavRow.svelte";
  import FolderIcon from "lucide-svelte/icons/folder";
  import { catchErrors } from "../../../frontend/Util/error";

  export let folder: Directory;
  /** Tree depth, 0 = top */
  export let indent = 0;
  /** Its subfolders are shown below it */
  export let expanded = false;
  export let selected = false;

  $: children = folder.subDirs;

  let contextMenu: ContextMenu;

  /** dragenter and dragleave also fire for the row's children */
  let dragDepth = 0;
  $: isDragOver = dragDepth > 0;
  function onDragEnter(event: DragEvent) {
    let types = event.dataTransfer.types;
    if (!types.includes("Files") && !types.includes("file/drag-ids")) {
      return;
    }
    dragDepth++;
  }
  function onDragLeave() {
    dragDepth = Math.max(dragDepth - 1, 0);
  }
  async function onDrop(event: DragEvent) {
    dragDepth = 0;
    await onDropFile(event, folder);
  }
</script>
