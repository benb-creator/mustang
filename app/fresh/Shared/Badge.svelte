<hbox class="badge {kind}" title={tooltip}>
  {count > 999 ? "999+" : count}
</hbox>

<script lang="ts">
  export let count: number;
  /** signal: new or unread items.
   * neutral: totals, counts in tabs.
   * accent: number of selected items.
   * danger: errors */
  export let kind: "signal" | "neutral" | "accent" | "danger" = "neutral";
  export let tooltip: string = null;
</script>

<style>
  .badge {
    flex: none;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
    height: 18px;
    min-width: 18px;
    padding: 0 6px;
    border-radius: 9px;
    font-size: var(--text-xs);
    line-height: 18px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .badge.signal {
    background-color: var(--signal);
    color: var(--fg-on-signal);
  }
  .badge.neutral {
    background-color: var(--fill-subtle);
    color: var(--fg-2);
  }
  .badge.accent {
    background-color: var(--accent);
    color: var(--fg-on-accent);
  }
  .badge.danger {
    background-color: var(--danger);
    color: var(--fg-on-accent);
  }
</style>
