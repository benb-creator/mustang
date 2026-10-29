<FolderPane bind:listFiles bind:listDirs {activeTab} bind:selectedFolder bind:selectedAccount
  let:accounts let:rootDirs>
  {#if activeTab == FilesView.CloudStorage}
    <AccountList {accounts} bind:selectedAccount>
      <FolderList slot="folders" folders={rootDirs} bind:selectedFolder bind:selectedFolders />
    </AccountList>
  {:else}
    <vbox flex class="harddrive">
      <FolderList folders={rootDirs} bind:selectedFolder bind:selectedFolders />
    </vbox>
  {/if}
  {#if selectedFolder}
    <vbox class="tags">
      <TagsList folder={selectedFolder} bind:searchFiles />
    </vbox>
  {/if}
</FolderPane>

<script lang="ts">
  import { File } from "../../../logic/Files/File";
  import { Directory } from "../../../logic/Files/Directory";
  import { FileOrDirectory } from "../../../logic/Files/FileOrDirectory";
  import { FileSharingAccount } from "../../../logic/Files/FileSharingAccount";
  import FolderPane from "../../../frontend/Files/FolderLeftPane/FolderPane.svelte";
  import AccountList from "./AccountList.svelte";
  import FolderList from "./FolderList.svelte";
  import TagsList from "../../../frontend/Files/FolderLeftPane/TagsList.svelte";
  import { FilesView } from "../../../frontend/Files/LeftPane/PaneViewSwitcher.svelte";
  import type { ArrayColl, Collection } from "svelte-collections";

  /** The list of files and folders to show on the right pane
   * in/out only */
  export let listFiles: Collection<File>;
  export let listDirs: Collection<Directory>;
  export let selectedFolder: Directory;
  export let activeTab: FilesView;

  let selectedAccount: FileSharingAccount;
  let selectedFolders: ArrayColl<Directory>;
  let searchFiles: ArrayColl<FileOrDirectory> | null;
</script>

<style>
  .harddrive {
    min-height: 0;
  }
  .tags {
    flex: none;
    padding-block: 4px 12px;
  }
</style>
