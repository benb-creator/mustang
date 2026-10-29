<vbox class="header">
  <h1>{title}</h1>
  <div class="subtitle">{subtitle}</div>
</vbox>

<script lang="ts">
  export let title: string;
  export let subtitle: string = "";
</script>

<style>
  .header {
    margin-block-end: 32px;
  }
  h1 {
    margin: 0px;
    font-size: 28px;
    letter-spacing: -0.5px;
  }
  .subtitle {
    margin-block-start: 2px;
    opacity: 65%;
    font-weight: 300;
    line-height: 1.4;
  }
  :global(.fresh) .header {
    margin-block-end: 24px;
  }
  :global(.fresh) .header h1 {
    font-size: var(--text-3xl);
    line-height: var(--line-3xl);
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--fg-1);
  }
  :global(.fresh) .subtitle {
    margin-block-start: 6px;
    opacity: 1;
    font-size: var(--text-l);
    line-height: var(--line-l);
    font-weight: 400;
    color: var(--fg-2);
  }
</style>
