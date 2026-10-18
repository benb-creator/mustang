<hbox class="time label">
  {time.toLocaleTimeString(getDateTimeLocale(), { hour: "numeric" })}
</hbox>

<script lang="ts">
  import { getDateTimeLocale } from "../../../l10n/l10n";

  export let time: Date
</script>

<style>
  .time {
    margin-block: -0.7em 0px;
    margin-inline: 8px 8px;
    color: var(--fg-muted);
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    justify-content: end;
  }
</style>
