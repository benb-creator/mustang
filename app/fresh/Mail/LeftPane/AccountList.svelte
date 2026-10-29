<AccountAccordion {accounts} bind:selectedAccount>
  <AccountListItem slot="account" let:account let:expanded let:onSelect
    {account}
    {expanded}
    on:click={onSelect}
    />
  <slot name="folders" slot="content" />
</AccountAccordion>

<script lang="ts">
  import type { MailAccount } from "../../../logic/Mail/MailAccount";
  import AccountListItem from "./AccountListItem.svelte";
  import AccountAccordion from "../../Shared/AccountAccordion.svelte";
  import type { Collection } from "svelte-collections";

  export let accounts: Collection<MailAccount>;
  export let selectedAccount: MailAccount; /* in/out */
</script>
