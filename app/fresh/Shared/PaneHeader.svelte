<hbox class="pane-header {level}" class:tall class:large class:loading>
  {#if $$slots.start}
    <hbox class="start">
      <slot name="start" />
    </hbox>
  {/if}
  {#if title}
    <hbox class="titles">
      <hbox class="title" title={title}>{title}</hbox>
      {#if subtitle}
        <hbox class="subtitle">{subtitle}</hbox>
      {/if}
    </hbox>
  {/if}
  <hbox class="middle" flex>
    <slot />
  </hbox>
  {#if $$slots.actions}
    <hbox class="actions">
      <slot name="actions" />
    </hbox>
  {/if}
</hbox>

<script lang="ts">
  export let title: string = null;
  /** Shown after the title, e.g. counts */
  export let subtitle: string = null;
  /** Which pane level the header sits on: navigation, list or content */
  export let level: "l1" | "l2" | "l3" = "l2";
  /** The height follows the content, for headers that show the object, e.g. a message or person */
  export let tall = false;
  /** Page title, e.g. of a settings page */
  export let large = false;
  /** Shows a running line at the bottom edge */
  export let loading = false;
</script>

<style>
  .pane-header {
    position: relative;
    flex: none;
    align-items: center;
    gap: 8px;
    box-sizing: border-box;
    height: var(--pane-header-height);
    min-width: 0;
    padding-inline: 16px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .pane-header.l1 {
    padding-inline: 12px;
    border-bottom: none;
  }
  .pane-header.l3 {
    padding-inline: 24px;
  }
  .pane-header.tall {
    height: auto;
    min-height: var(--pane-header-height);
    align-items: start;
    padding-block: 12px;
  }
  .start,
  .actions {
    flex: none;
    align-items: center;
    gap: 4px;
  }
  .titles {
    align-items: baseline;
    gap: 8px;
    min-width: 0;
  }
  .title {
    display: block;
    min-width: 0;
    font-size: var(--text-xl);
    line-height: var(--line-xl);
    font-weight: 600;
    color: var(--fg-1);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .pane-header.large .title {
    font-size: var(--text-2xl);
    line-height: var(--line-2xl);
    letter-spacing: -0.01em;
  }
  .subtitle {
    flex: none;
    font-size: var(--text-s);
    line-height: var(--line-s);
    color: var(--fg-2);
    white-space: nowrap;
  }
  .middle {
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .pane-header.tall .middle {
    align-items: start;
  }
  .loading::after {
    content: "";
    position: absolute;
    inset-inline: 0;
    bottom: -1px;
    height: 2px;
    background: linear-gradient(90deg, transparent 0 30%, var(--accent) 30% 62%, transparent 62%);
    background-size: 200% 100%;
    animation: pane-header-loading 1.2s linear infinite;
  }
  @keyframes pane-header-loading {
    from {
      background-position: 100% 0;
    }
    to {
      background-position: -100% 0;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .loading::after {
      animation: none;
      background: linear-gradient(90deg, var(--accent) 0 40%, transparent 40%);
    }
  }
</style>
