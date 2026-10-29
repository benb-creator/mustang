<AccountList {accounts} bind:selectedAccount>
  <AccountAccordion {accounts} bind:selectedAccount>
    <AccountListItem slot="account" let:account let:expanded let:onSelect
      {account}
      {expanded}
      on:click={onSelect}
      />
    <slot name="folders" slot="content" />
  </AccountAccordion>
</AccountList>

<script lang="ts">
  import type { FileSharingAccount } from "../../../logic/Files/FileSharingAccount";
  import AccountList from "../../../frontend/Files/FolderLeftPane/AccountList.svelte";
  import AccountListItem from "./AccountListItem.svelte";
  import AccountAccordion from "../../Shared/AccountAccordion.svelte";
  import type { Collection } from "svelte-collections";

  export let accounts: Collection<FileSharingAccount>;
  export let selectedAccount: FileSharingAccount; /* in/out */
</script>
