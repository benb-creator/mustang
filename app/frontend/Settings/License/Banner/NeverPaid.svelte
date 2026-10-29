<hbox class="payment-bar">
  <hbox flex />
  <div class="message">{message ?? $t`You can buy a license for ${appName} at our website`}</div>
  <hbox flex />
  <Button
    label={$t`Buy`}
    onClick={() => openPurchasePage(paid => license = paid)}
    classes="filled"
    />
</hbox>

<script lang="ts">
  import { Ticket, openPurchasePage } from "../../../../logic/util/LicenseClient";
  import { appName } from "../../../../logic/build";
  import Button from "../../../Shared/Button.svelte";
  import { t } from "../../../../l10n/l10n";

  export let license: Ticket;
  export let message: string = undefined;
</script>

<style>
  .payment-bar {
    padding: 6px 12px 6px 16px;
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
