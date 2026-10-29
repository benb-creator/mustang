<h2 class="page-title">{$t`Sharing *=> Teammates that can access your mailbox`}</h2>
<hbox class="subtitle font-small">{$t`Select the people who have access to your mails, calendar and contacts, or access theirs`}</hbox>

{#if account.isDependentAccount}
  This is the shared account of {account.username}.
  You access it from main account {account.mainAccount.name}.
  <!-- TODO make it clickable to navigate to main account Sharing settings -->
{:else}
  <SharingIncoming {account}  />
  <SharingOutgoing {account} />
{/if}

<script lang="ts">
  import type { MailAccount } from "../../../logic/Mail/MailAccount";
  import SharingIncoming from "./SharingIncoming.svelte";
  import SharingOutgoing from "./SharingOutgoing.svelte";
  import { t } from "../../../l10n/l10n";

  export let account: MailAccount;
</script>

<style>
  h2 {
    margin-block-end: 0;
  }
  .subtitle {
    opacity: 70%;
    margin-block-end: 20px;
  }
  :global(.fresh) .page-title {
    display: none;
  }
  :global(.fresh) .subtitle {
    margin-block: 16px 8px;
    color: var(--fg-2);
    font-size: var(--text-l);
    line-height: var(--line-l);
  }
</style>
