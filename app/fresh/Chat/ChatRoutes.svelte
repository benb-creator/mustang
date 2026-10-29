<Route path="/">
  <ChatAppD>
    <Header slot="header" let:accounts {accounts} bind:selectedAccount={$selectedAccount} />
  </ChatAppD>
</Route>

<script lang="ts">
  import { selectedAccount } from "../../frontend/Chat/selected";
  import ChatAppD from "../../frontend/Chat/ChatAppD.svelte";
  import Header from "./Header.svelte";
  import { Route } from "svelte-navigator";
</script>
