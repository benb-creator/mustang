<hbox class="payment-bar thankyou">
  <hbox flex />
  <div class="message">{$t`Thank you for your purchase.`}</div>
  <HeartIcon />
  <hbox flex />
</hbox>

<script lang="ts">
  import HeartIcon from "lucide-svelte/icons/heart";
  import { t } from "../../../../l10n/l10n";
</script>

<style>
  .payment-bar {
    padding: 6px 16px;
    align-items: center;
    background-color: turquoise;
    color: #160C27;
  }
  .thankyou :global(svg) {
    fill: red;
    stroke: #FF000033;
    margin-inline-start: 8px;
  }
  :global(.fresh) .payment-bar {
    gap: 12px;
    box-sizing: border-box;
    min-height: 40px;
    padding: 4px 8px 4px 16px;
    border: 1px solid color-mix(in srgb, var(--success-fg) 30%, transparent);
    border-radius: var(--radius-m);
    background-color: var(--success-tint);
    color: var(--fg-1);
  }
  :global(.fresh) .thankyou :global(svg) {
    width: 16px;
    height: 16px;
    margin-inline-start: 0;
    fill: var(--danger-fg);
    stroke: var(--danger-fg);
  }
</style>
