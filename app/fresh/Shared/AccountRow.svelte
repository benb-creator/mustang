<hbox class="account-row"
  class:expanded
  class:has-actions={$$slots.actions}
  title={tooltip ?? $account.name}
  on:click={onExpandToggle}
  on:click
  on:contextmenu
  on:dragenter
  on:dragover
  on:dragleave
  on:drop
  >
  <button class="expander"
    title={expanded ? $t`Collapse` : $t`Expand`}
    aria-expanded={expanded}
    tabindex={-1}
    >
    <ChevronIcon size="16px" />
  </button>
  {#if $account.icon && typeof($account.icon) == "string"}
    <img class="picture" src={$account.icon} width="18" height="18" alt="" />
  {:else}
    <hbox class="swatch" style:background-color={$account.color} />
  {/if}
  <hbox class="name">{$account.name}</hbox>
  {#if !$account.isLoggedIn}
    <hbox class="logged-out" title={$t`Not logged in`}>
      <LoggedOutIcon size="14px" />
    </hbox>
  {/if}
  {#if count}
    <hbox class="count">
      <Badge {count} kind="signal" />
    </hbox>
  {/if}
  {#if $$slots.actions}
    <hbox class="actions">
      <slot name="actions" />
    </hbox>
  {/if}
</hbox>

<script lang="ts">
  import type { Account } from "../../logic/Abstract/Account";
  import Badge from "./Badge.svelte";
  import ChevronIcon from "lucide-svelte/icons/chevron-right";
  import LoggedOutIcon from "lucide-svelte/icons/plug-zap";
  import { t } from "../../l10n/l10n";

  export let account: Account;
  /** Whether the account's content is shown below
   * in/out */
  export let expanded = false;
  /** Number of new or unread items in this account */
  export let count: number = 0;
  /** Default: the account name */
  export let tooltip: string = null;

  function onExpandToggle() {
    expanded = !expanded;
  }
</script>

<style>
  .account-row {
    position: relative;
    flex: none;
    align-items: center;
    gap: 6px;
    box-sizing: border-box;
    height: 36px;
    min-width: 0;
    padding-inline: 12px;
    font-weight: 600;
    color: var(--fg-2);
    white-space: nowrap;
    cursor: default;
  }
  .account-row.expanded {
    color: var(--fg-1);
  }
  .account-row:hover {
    background-color: var(--row-hover);
  }
  .expander {
    flex: none;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    padding: 0;
    border: none;
    background-color: transparent;
    color: var(--fg-3);
    cursor: pointer;
    transition: transform var(--motion-fast) var(--motion-ease);
  }
  :global([dir="rtl"]) .expander {
    transform: scaleX(-1);
  }
  .account-row.expanded .expander {
    transform: rotate(90deg);
  }
  .swatch {
    flex: none;
    width: 10px;
    height: 10px;
    margin-inline: 4px;
    border-radius: 2px;
  }
  .picture {
    flex: none;
    border-radius: 2px;
  }
  .name {
    display: block;
    flex: 1 1 0;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .logged-out {
    flex: none;
    color: var(--warning-fg);
  }
  .count,
  .actions {
    flex: none;
    align-items: center;
  }
  .actions {
    gap: 2px;
    margin-inline-end: -6px;
    font-weight: 400;
  }
  .account-row:not(.expanded):not(:hover):not(:has(:focus-visible)) .actions {
    display: none;
  }
  .account-row.expanded:not(:hover):not(:has(:focus-visible)) .actions {
    position: absolute;
    inset-inline-end: 12px;
    opacity: 0;
    pointer-events: none;
  }
  .account-row.has-actions:hover .count,
  .account-row.has-actions:has(:focus-visible) .count {
    display: none;
  }
  @container (max-width: 120px) {
    .account-row {
      justify-content: center;
      padding-inline: 4px;
    }
    .expander,
    .name,
    .actions {
      display: none;
    }
    .count {
      position: absolute;
      top: 1px;
      inset-inline-end: 4px;
    }
  }
</style>
