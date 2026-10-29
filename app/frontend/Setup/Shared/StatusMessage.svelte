<hbox flex class="status {status}">
  {#if status == "processing"}
    <hbox class="spinner">
      <Spinner size="24px" />
    </hbox>
  {/if}
  <hbox flex class="box">
    <hbox class="icon">
      <slot name="icon" />
    </hbox>
    {#if message}
      <hbox class="message value">
        {message}
      </hbox>
    {/if}
    <slot />
  </hbox>
</hbox>

<script lang="ts">
  import Spinner from "../../Shared/Spinner.svelte";

  export let message: string = null;
  export let status: "success" | "processing" | "error" | "warning" | "" = "";
</script>

<style>
  .status {
    margin-block-start: 8px;
    margin-block-end: 8px;
  }
  .box {
    border-radius: 8px;
    justify-content: start;
    margin-inline-start: 8px;
    margin-inline-end: 24px;
    padding: 6px 16px 6px 12px;
  }
  .spinner {
    margin: 4px;
  }
  .message {
    overflow-wrap: anywhere;
  }
  .success .box {
    background-color: #E7F9EC;
    color: #044f1a;
    border: 1px solid #0BC24180;
  }
  .processing .box {
    background-color: #F0F9F8;
    color: #455468;
    margin-inline-start: 16px;
  }
  .warning .box,
  .error .box {
    background-color: #F8FFD2;
    color: #DD0000;
    border: 1px solid #FFC83A;
    max-width: 40em;
  }
  .error .box :global(.button) {
    color: #AA0000;
  }
  @media (prefers-color-scheme: dark) {
    .success .box,
    .processing .box,
    .warning .box,
    .error .box {
      background-color: unset;
    }
    .warning .box,
    .error .box {
      color: #FF3333;
    }
    .error .box :global(.button) {
      color: #FFC83A;
    }
  }
  .icon {
    margin-inline-end: 6px;
  }
  :global(.fresh) .status {
    margin-block: 12px;
  }
  :global(.fresh) .box {
    align-items: center;
    gap: 8px;
    margin-inline: 0;
    padding: 8px 12px;
    border: 1px solid transparent;
    border-radius: var(--radius-m);
    font-size: var(--text-m);
    line-height: var(--line-m);
  }
  :global(.fresh) .spinner {
    margin: 0 8px 0 0;
  }
  :global(.fresh) .icon {
    margin-inline-end: 0;
  }
  :global(.fresh) .icon :global(svg) {
    width: 16px;
    height: 16px;
  }
  :global(.fresh) .success .box {
    border-color: color-mix(in srgb, var(--success-fg) 30%, transparent);
    background-color: var(--success-tint);
    color: var(--fg-1);
  }
  :global(.fresh) .success .icon {
    color: var(--success-fg);
  }
  :global(.fresh) .processing .box {
    margin-inline: 0;
    padding-inline: 0;
    background-color: transparent;
    color: var(--fg-2);
    font-size: var(--text-l);
  }
  :global(.fresh) .warning .box {
    max-width: none;
    border-color: color-mix(in srgb, var(--warning-fg) 30%, transparent);
    background-color: var(--warning-tint);
    color: var(--fg-1);
  }
  :global(.fresh) .warning .icon {
    color: var(--warning-fg);
  }
  :global(.fresh) .error .box {
    max-width: none;
    border-color: color-mix(in srgb, var(--danger-fg) 30%, transparent);
    background-color: var(--danger-tint);
    color: var(--fg-1);
  }
  :global(.fresh) .error .icon {
    color: var(--danger-fg);
  }
  :global(.fresh) .error .box :global(.button) {
    color: var(--danger-fg);
  }
</style>
