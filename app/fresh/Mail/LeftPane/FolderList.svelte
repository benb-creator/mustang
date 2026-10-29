<vbox flex class="folders">
  <FolderList {folders} bind:selectedFolder bind:selectedFolders>
    <FolderLine slot="row" let:folder let:indentionLevel
      folder={folder as Folder}
      indent={indentionLevel}
      expanded={isOnPathTo(folder as Folder, selectedFolder)}
      selected={folder == selectedFolder}
      {nextLevel}
      on:click>
      <slot name="buttons" slot="buttons" let:folder {folder} />
    </FolderLine>
  </FolderList>
</vbox>

<script lang="ts">
  import type { Folder } from "../../../logic/Mail/Folder";
  import FolderList from "../../../frontend/Mail/LeftPane/FolderList.svelte";
  import { isOnPathTo } from "../../../frontend/Shared/FastTree";
  import FolderLine from "./FolderLine.svelte";
  import type { Collection, ArrayColl } from "svelte-collections";

  export let folders: Collection<Folder>;
  export let selectedFolder: Folder; /* in/out */
  export let selectedFolders: ArrayColl<Folder>;
  export let nextLevel: "l2" | "l3" = "l2";
</script>

<style>
  .folders {
    min-height: 90px;
  }
  .folders :global(.fast-list .header) {
    display: none;
  }
  .folders :global(.fast-list .row > *) {
    padding: 0;
  }
  .folders :global(.fast-list:focus-visible) {
    outline-offset: -2px;
  }
</style>
