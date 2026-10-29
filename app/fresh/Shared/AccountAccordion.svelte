<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<vbox flex class="account-accordion"
  tabindex={0}
  bind:this={accordionE}
  on:keydown={onKey}
  >
  {#each $accounts.each as account (account)}
    <slot name="account" {account}
      expanded={account == selectedAccount && !isCollapsed}
      onSelect={() => onSelect(account)}
      />
    {#if account == selectedAccount && !isCollapsed}
      <slot name="content" {account} />
    {/if}
  {/each}
</vbox>

<script lang="ts">
  import type { Account } from "../../logic/Abstract/Account";
  import type { Collection } from "svelte-collections";

  type T = $$Generic<Account>;

  export let accounts: Collection<T>;
  /** in/out */
  export let selectedAccount: T;

  /** The user closed the selected account */
  let isCollapsed = false;
  let accordionE: HTMLElement;

  function onSelect(account: T) {
    if (account == selectedAccount) {
      isCollapsed = !isCollapsed;
      return;
    }
    selectedAccount = account;
    isCollapsed = false;
  }

  function onKey(event: KeyboardEvent) {
    let step = event.key == "ArrowDown" ? 1 : event.key == "ArrowUp" ? -1 : 0;
    if (!step || event.target != accordionE) {
      return;
    }
    event.preventDefault();
    let all = accounts.contents;
    let next = all[all.indexOf(selectedAccount) + step];
    if (!next) {
      return;
    }
    selectedAccount = next;
    isCollapsed = false;
  }
</script>

<style>
  .account-accordion {
    min-height: 0;
    overflow-y: auto;
  }
  .account-accordion:focus-visible {
    outline-offset: -2px;
  }
</style>
