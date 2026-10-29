<vbox flex class="left-pane">
  <slot name="top">
    <hbox class="top">
      <vbox class="island">
        <PaneViewSwitcher bind:active={activeTab} />
      </vbox>
      <hbox flex />
    </hbox>
  </slot>

  {#if activeTab == FilesView.Recent}
    <RecentList />
  {:else if activeTab == FilesView.Person}
    <PersonsPane bind:listFiles bind:listDirs />
  {:else if activeTab == FilesView.Project}
    <!---->
  {:else if activeTab == FilesView.Search}
    <SearchPane bind:listFiles bind:listDirs on:clear={endSearchMode} />
  {:else if activeTab == FilesView.CloudStorage || activeTab == FilesView.Harddrive}
    <slot name="folder-pane">
      <FolderPane bind:listFiles bind:listDirs {activeTab} bind:selectedFolder={$selectedFolder} />
    </slot>
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
    box-shadow: var(--left-pane-shadow, 2px 0px 6px 0px rgba(0, 0, 0, 10%));
    background-color: var(--leftbar-bg);
    color: var(--leftbar-fg);
    padding-block-end: 16px;
    margin: var(--pane-margin);
  }

  .left-pane :global(.persons) {
    margin-block-start: 8px;
  }
  :global(.lookout-window) .left-pane :global(.persons) {
    margin-block-start: 0;
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
  :global(.fresh) .left-pane {
    min-width: 0;
    min-height: 0;
    margin: 0;
    padding-block-end: 0;
    background-color: var(--l1-bg);
    color: var(--l1-fg);
    box-shadow: inset -1px 0 0 var(--border);
    container-type: inline-size;
  }
  :global(.fresh[dir="rtl"]) .left-pane {
    box-shadow: inset 1px 0 0 var(--border);
  }
  :global(.fresh) .left-pane :global(.persons),
  :global(.fresh) .left-pane :global(.account-list),
  :global(.fresh) .left-pane > :global(.search) {
    margin-block-start: 0;
  }
  :global(.fresh) .left-pane :global(.persons .search) {
    margin-block-start: 8px;
  }
  @container (max-width: 120px) {
    :global(.fresh) .left-pane :global(.pane-header) {
      padding-inline: 4px;
    }
  }
</style>
