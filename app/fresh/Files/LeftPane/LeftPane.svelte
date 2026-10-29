<LeftPane bind:listFiles bind:listDirs bind:activeTab>
  <PaneHeader level="l1" slot="top">
    <hbox flex class="mode-switcher">
      <PaneViewSwitcher bind:active={activeTab} />
    </hbox>
  </PaneHeader>
  <FolderPane slot="folder-pane" bind:listFiles bind:listDirs {activeTab} bind:selectedFolder={$selectedFolder} />
</LeftPane>

<script lang="ts">
  import { File } from "../../../logic/Files/File";
  import { Directory } from "../../../logic/Files/Directory";
  import { selectedFolder } from "../../../frontend/Files/selected";
  import LeftPane from "../../../frontend/Files/LeftPane/LeftPane.svelte";
  import FolderPane from "../FolderLeftPane/FolderPane.svelte";
  import PaneViewSwitcher, { FilesView } from "../../../frontend/Files/LeftPane/PaneViewSwitcher.svelte";
  import PaneHeader from "../../Shared/PaneHeader.svelte";
  import type { Collection } from "svelte-collections";

  /** The list of files and folders to show on the right pane
   * in/out only */
  export let listFiles: Collection<File>;
  export let listDirs: Collection<Directory>;
  export let activeTab: FilesView;
</script>

<style>
  .mode-switcher {
    min-width: 0;
  }
  .mode-switcher > :global(.island) {
    flex: 1 1 0;
    min-width: 0;
  }
  .mode-switcher :global(.island.specific > .button.selected) {
    flex: 1 1 0;
    min-width: 0;
  }
  @container (max-width: 200px) {
    .mode-switcher :global(.island.specific > .button.selected .label) {
      display: none;
    }
  }
  @container (max-width: 120px) {
    .mode-switcher :global(.island.specific) {
      flex-wrap: wrap;
    }
  }
</style>
