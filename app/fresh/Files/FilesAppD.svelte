<FrontendFilesAppD bind:listFiles bind:listDirs>
  <LeftPane slot="left-pane" bind:listFiles bind:listDirs bind:activeTab={$selectedLeftTab} />
</FrontendFilesAppD>

<script lang="ts">
  import type { File } from "../../logic/Files/File";
  import type { Directory } from "../../logic/Files/Directory";
  import { selectedLeftTab } from "../../frontend/Files/selected";
  import FrontendFilesAppD from "../../frontend/Files/FilesAppD.svelte";
  import LeftPane from "./LeftPane/LeftPane.svelte";
  import type { Collection } from "svelte-collections";

  let listFiles: Collection<File>;
  let listDirs: Collection<Directory>;
</script>
