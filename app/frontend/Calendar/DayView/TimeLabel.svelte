<hbox class="time label">
  {time.toLocaleTimeString(getDateTimeLocale(), { hour: "numeric" })}
</hbox>

<script lang="ts">
  import { getDateTimeLocale } from "../../../l10n/l10n";

  export let time: Date
</script>

<style>
  .time {
    margin: -0.8em 8px 0 0;
    color: #AAABB4;
    font-weight: 300;
    justify-content: end;
  }
  :global(.fresh) .time {
    box-sizing: border-box;
    width: 56px;
    margin: -0.6em 0 0 0;
    padding-inline-end: 8px;
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-weight: 400;
    font-variant-numeric: tabular-nums;
    color: var(--fg-3);
  }
</style>
