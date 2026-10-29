<FolderPropertiesPage bind:folder bind:selectedAccount {accounts}>
  <svelte:fragment slot="folder-pane" let:folders>
    <AccountList {accounts} bind:selectedAccount>
      <FolderList slot="folders" {folders} bind:selectedFolder={folder} bind:selectedFolders nextLevel="l3" />
    </AccountList>
  </svelte:fragment>
</FolderPropertiesPage>

<script lang="ts">
  import type { Folder } from "../../logic/Mail/Folder";
  import type { MailAccount } from "../../logic/Mail/MailAccount";
  import FolderPropertiesPage from "../../frontend/Mail/FolderPropertiesPage.svelte";
  import AccountList from "./LeftPane/AccountList.svelte";
  import FolderList from "./LeftPane/FolderList.svelte";
  import type { ArrayColl, Collection } from "svelte-collections";

  export let folder: Folder; /** in/out */
  export let accounts: Collection<MailAccount>; /** in */
  export let selectedAccount: MailAccount; /** in/out */

  let selectedFolders: ArrayColl<Folder>;
</script>
