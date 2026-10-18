<vbox flex class="left-pane nav-list">
  <hbox class="top">
    <vbox class="island">
      <PaneViewSwitcher bind:active={activeTab} />
    </vbox>
    <hbox flex />
  </hbox>

  {#if activeTab == FilesView.Recent}
    <RecentList />
  {:else if activeTab == FilesView.Person}
    <PersonsPane bind:listFiles bind:listDirs />
  {:else if activeTab == FilesView.Project}
    <!---->
  {:else if activeTab == FilesView.Search}
    <SearchPane bind:listFiles bind:listDirs on:clear={endSearchMode} />
  {:else if activeTab == FilesView.CloudStorage || activeTab == FilesView.Harddrive}
    <FolderPane bind:listFiles bind:listDirs {activeTab} bind:selectedFolder={$selectedFolder} />
  {/if}
</vbox>

<script lang="ts">
  import { File } from "../../../logic/Files/File";
  import { Directory } from "../../../logic/Files/Directory";
  import { selectedFolder } from "../selected";
  import { globalSearchTerm } from "../../AppsBar/selectedApp";
  import FolderPane from "../FolderLeftPane/FolderPane.svelte";
  import SearchPane from "../Search/SearchPane.svelte";
  import RecentList from "./RecentList.svelte";
  import PersonsPane from "./PersonsPane.svelte";
  import PaneViewSwitcher, { FilesView } from "./PaneViewSwitcher.svelte";
  import { Collection } from 'svelte-collections';

  /** The list of files and folders to show on the right pane
   * in/out only */
  export let listFiles: Collection<File>;
  export let listDirs: Collection<Directory>;
  export let activeTab: FilesView;

  $: if (!!$globalSearchTerm) openSearchPane();
  function openSearchPane() {
    activeTab = FilesView.Search;
  }
  function endSearchMode() {
    activeTab = FilesView.Harddrive;
  }
</script>

<style>
  .left-pane {
    border-inline-end: 1px solid var(--border);
    background-color: var(--leftbar-bg);
    color: var(--leftbar-fg);
    padding-block-end: 16px;
  }

  .left-pane :global(.persons) {
    margin-block-start: 8px;
  }
  .left-pane :global(.account-list) {
    margin-block-start: -4px;
  }
  .left-pane :global(.search) {
    margin-block-start: -2px;
  }
  .top :global(.svelteui-Tab) {
    padding: 8px 12px;
    height: unset;
  }
  .island {
    margin: 8px 12px;
  }
</style>
