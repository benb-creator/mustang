<hbox class="payment-bar">
  <hbox flex />
  <div class="message">{$t`Upgrade your license from Owl to ${appName}`}</div>
  <hbox flex />
  <Button
    label={$t`Upgrade`}
    onClick={() => openPurchasePage(paid => license = paid)}
    />
</hbox>

<script lang="ts">
  import { Ticket, openPurchasePage } from "../../../../logic/util/LicenseClient";
  import { appName } from "../../../../logic/build";
  import Button from "../../../Shared/Button.svelte";
  import { t } from "../../../../l10n/l10n";

  export let license: Ticket;
  export let owlLicense: Ticket;
</script>

<style>
  .payment-bar {
    padding: 6px 16px;
    align-items: center;
    background-color: #FFF160;
    color: #160C27;
    border-radius: inherit;
  }
  .payment-bar :global(button) {
    padding: 2px 12px !important;
  }
  :global(.fresh) .payment-bar {
    gap: 12px;
    box-sizing: border-box;
    min-height: 40px;
    padding: 4px 8px 4px 16px;
    border: 1px solid color-mix(in srgb, var(--info-fg) 30%, transparent);
    border-radius: var(--radius-m);
    background-color: var(--info-tint);
    color: var(--fg-1);
  }
</style>
