<FolderLine {folder} let:folderName let:tooltip let:isNormalFolderOrInbox let:contextMenu>
  <NavRow
    label={folderName}
    {tooltip}
    count={isNormalFolderOrInbox ? $folder.countNewArrived : 0}
    countKind="new"
    {indent}
    expandable={$children.hasItems}
    {expanded}
    expanderToggles={false}
    {selected}
    {nextLevel}
    dropTarget={isDragOver}
    on:click
    on:contextmenu={event => contextMenu.onContextMenu(event)}
    on:dragenter={onDragEnter}
    on:dragleave={onDragLeave}
    on:dragover={(event) => catchErrors(() => onDragOverMail(event, folder))}
    on:drop={(event) => catchErrors(() => onDrop(event))}
    >
    <FolderIcon slot="icon" {folder} size="16px" />
    <slot name="buttons" slot="actions" {folder} />
  </NavRow>
</FolderLine>

<script lang="ts">
  import type { Folder } from "../../../logic/Mail/Folder";
  import { onDropMail, onDragOverMail } from "../../../frontend/Mail/Message/drag";
  import FolderLine from "../../../frontend/Mail/LeftPane/FolderLine.svelte";
  import FolderIcon from "../../../frontend/Mail/LeftPane/FolderIcon.svelte";
  import NavRow from "../../Shared/NavRow.svelte";
  import { catchErrors } from "../../../frontend/Util/error";

  export let folder: Folder;
  /** Tree depth, 0 = top */
  export let indent = 0;
  export let expanded = false;
  export let selected = false;
  /** The level the folder opens: the message list or a page */
  export let nextLevel: "l2" | "l3" = "l2";

  $: children = folder.subFolders;

  /** dragenter and dragleave also fire for the row's children */
  let dragDepth = 0;
  $: isDragOver = dragDepth > 0;
  function onDragEnter(event: DragEvent) {
    if (!event.dataTransfer.types.includes("message/drag-ids")) {
      return;
    }
    dragDepth++;
  }
  function onDragLeave() {
    dragDepth = Math.max(dragDepth - 1, 0);
  }
  async function onDrop(event: DragEvent) {
    dragDepth = 0;
    await onDropMail(event, folder);
  }
</script>
