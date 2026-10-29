<hbox class="identity-selector">
  {#if selectedIdentity.isCatchAll}
    <label for="customFrom">{$t`From`}</label>
    <hbox class="before-custom">{beforeCustom}</hbox>
    <input type="email" bind:value={editableCustom}
      name="customFrom" spellcheck="false"
      on:change={() => catchErrors(onCustomEdited)}
      size={editableCustom?.length || 10}
      />
    <hbox class="after-custom">{afterCustom}</hbox>
    <hbox class="account">
      {selectedIdentity.account?.name}
    </hbox>
  {/if}
  {#if $identities.length > 1}
    <select bind:value={selectedIdentity} class:catch-all={selectedIdentity.isCatchAll}>
      {#each $identities.each as identity }
        <option value={identity}>
          {identity.isCatchAll && identity.isEMailAddress(fromAddress) && identity.emailAddress != fromAddress
            ? fromAddress
            : identity.name}
          -
          {identity.account?.name}
        </option>
      {/each}
    </select>
  {/if}
</hbox>

<script lang="ts">
  import { findAllIdentities, type MailIdentity } from "../../../logic/Mail/MailIdentity";
  import { catchErrors } from "../../Util/error";
  import type { Collection } from "svelte-collections";
  import { t } from "../../../l10n/l10n";

  export let selectedIdentity: MailIdentity; /* in/out */
   /** Which identities to select from.
    * Default: all identities of all accounts
    * in */
  export let identities: Collection<MailIdentity> = findAllIdentities();
  /** Allows the user to override the From address with a custom email address.
   * This allows for catch-all email addresses to be used as From: */
  export let fromAddress: string;
  export let fromName: string;

  let beforeCustom: string;
  let afterCustom: string;
  let editableCustom: string;

  $: $selectedIdentity && setIdentity($selectedIdentity)
  function setIdentity(identity: MailIdentity) {
    fromName = identity.realname;
    if (!identity?.isCatchAll) {
      fromAddress = identity.emailAddress;
      return;
    }
    if (!identity.isEMailAddress(fromAddress)) {
      fromAddress = identity.emailAddress;
    }

    let parts = identity.emailAddress.split("*");
    beforeCustom = parts[0];
    afterCustom = parts[1];
    editableCustom = fromAddress.substring(beforeCustom.length, fromAddress.length - afterCustom.length);
  }

  function onCustomEdited() {
    fromAddress = beforeCustom + editableCustom + afterCustom;
  }
</script>

<style>
  .identity-selector {
    align-items: center;
  }
  .identity-selector select {
    border: none;
    color: inherit;
    background-color: transparent;
  }
  label {
    margin-inline-end: 12px;
  }
  input[type=email] {
    min-width: 20vw;
    width: 20%;
  }
  .before-custom,
  .after-custom,
  .account {
    overflow-x: hidden; /* TODO not working. Problem: Mobile, with long domains. */
  }
  select.catch-all {
    width: 20px;
    height: 100%;
  }
  .account {
    margin-inline-start: 16px;
    font-style: italic;
    opacity: 75%;
  }

  :global(.fresh) .identity-selector {
    gap: 4px;
    min-width: 0;
  }
  :global(.fresh) .identity-selector select {
    min-width: 0;
    max-width: 480px;
    height: var(--control-height);
    padding: 0 6px 0 10px;
    border: 1px solid var(--border-input);
    border-radius: var(--radius-m);
    background-color: var(--input-bg);
    color: var(--fg-1);
  }
  :global(.fresh) .identity-selector select:hover {
    border-color: var(--fg-3);
  }
  :global(.fresh) .identity-selector select:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }
  :global(.fresh) .identity-selector label {
    margin-inline-end: 4px;
    font-size: var(--text-s);
    font-weight: 600;
    color: var(--fg-3);
  }
  :global(.fresh) .identity-selector input[type=email] {
    min-width: 8em;
    width: auto;
  }
  :global(.fresh) .before-custom,
  :global(.fresh) .after-custom {
    color: var(--fg-2);
  }
  :global(.fresh) select.catch-all {
    width: 30px;
    padding: 0 4px;
  }
  :global(.fresh) .account {
    margin-inline-start: 8px;
    font-style: normal;
    color: var(--fg-2);
    opacity: 1;
  }
</style>
