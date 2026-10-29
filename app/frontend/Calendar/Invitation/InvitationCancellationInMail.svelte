<hbox class="cancelled-invitation">
  <hbox class="cancelled-text">
    {$t`This meeting has been cancelled by the organizer`}
  </hbox>
</hbox>

<script lang="ts">
  import { t } from "../../../l10n/l10n";
</script>

<style>
  .cancelled-invitation {
    align-items: center;
    justify-content: center;
    margin-block-start: 16px;
  }
  .cancelled-text {
    flex-wrap: wrap;
    background-color: rgba(255, 166, 0, 0.291);
    padding: 8px 12px;
    border-radius: 3px;
    margin: 8px;
  }
  :global(.fresh) .cancelled-text {
    border: 1px solid color-mix(in srgb, var(--warning-fg) 30%, transparent);
    border-radius: var(--radius-m);
    background-color: var(--warning-tint);
    color: var(--fg-1);
  }
</style>
