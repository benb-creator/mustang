<Header bind:selectedAccount {accounts} menuPlacement="bottom-start">
  <Button
    slot="new-chat"
    let:toggleNewChatMenu
    label={$t`New chat`}
    icon={NewChatIcon}
    classes="primary"
    onClick={toggleNewChatMenu}
    />
</Header>

<script lang="ts">
  import type { ChatAccount } from "../../logic/Chat/ChatAccount";
  import Header from "../../frontend/Chat/Header.svelte";
  import Button from "../../frontend/Shared/Button.svelte";
  import NewChatIcon from "lucide-svelte/icons/message-square-plus";
  import type { Collection } from "svelte-collections";
  import { t } from "../../l10n/l10n";

  export let accounts: Collection<ChatAccount>;
  export let selectedAccount: ChatAccount; /* in/out */
</script>
