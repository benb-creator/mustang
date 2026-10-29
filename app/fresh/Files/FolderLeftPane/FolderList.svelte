<FolderList {folders} bind:selectedFolder bind:selectedFolders>
  <FolderLine slot="row" let:folder let:indentionLevel
    folder={folder as Directory}
    indent={indentionLevel}
    expanded={isOnPathTo(folder as Directory, selectedFolder)}
    selected={folder == selectedFolder}
    />
</FolderList>

<script lang="ts">
  import type { Directory } from "../../../logic/Files/Directory";
  import FolderList from "../../../frontend/Files/FolderLeftPane/FolderList.svelte";
  import FolderLine from "./FolderLine.svelte";
  import { isOnPathTo } from "../../../frontend/Shared/FastTree";
  import type { Collection, ArrayColl } from "svelte-collections";

  export let folders: Collection<Directory>;
  export let selectedFolder: Directory; /* in/out */
  export let selectedFolders: ArrayColl<Directory>;
</script>
