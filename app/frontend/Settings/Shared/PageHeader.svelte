<hbox class="title">
  <slot name="title" />
  {title}
  <hbox flex />
  <hbox class="buttons">
    <slot name="buttons-top-right" />
  </hbox>
</hbox>
<hbox class="subtitle font-normal">
  <slot name="subtitle" />
  {subtitle}
</hbox>

<script lang="ts">
  export let title = "";
  export let subtitle = "";
</script>

<style>
  .title {
    font-size: 32px;
  }
  .subtitle {
  }
  .buttons {
    justify-content: center;
    align-items: center;
  }
  /* Hides the title text, which the pane header shows, but keeps the buttons */
  :global(.fresh) .title {
    order: -1;
    justify-content: end;
    min-height: 0;
    font-size: 0;
    line-height: 0;
  }
  :global(.fresh) .buttons {
    gap: 4px;
    font-size: var(--text-m);
    line-height: var(--line-m);
  }
  :global(.fresh) .subtitle {
    order: -2;
    margin-block: 16px 8px;
    color: var(--fg-2);
    font-size: var(--text-l);
    line-height: var(--line-l);
  }
</style>
