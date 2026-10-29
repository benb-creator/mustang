<vbox class="empty-state">
  {#if typeof(icon) == "string"}
    <hbox class="icon">
      <Icon data={icon} size="32px" />
    </hbox>
  {:else if icon}
    <hbox class="icon">
      <svelte:component this={icon} size="32px" strokeWidth={1.5} />
    </hbox>
  {/if}
  {#if title}
    <hbox class="title">{title}</hbox>
  {/if}
  {#if text}
    <hbox class="text">{text}</hbox>
  {/if}
  <slot />
  {#if $$slots.action}
    <hbox class="action">
      <slot name="action" />
    </hbox>
  {/if}
</vbox>

<script lang="ts">
  import Icon from "../../frontend/Shared/Icon.svelte";

  export let icon: ConstructorOfATypedSvelteComponent | string = null;
  export let title: string = null;
  export let text: string = null;
</script>

<style>
  .empty-state {
    align-items: center;
    justify-content: center;
    gap: 8px;
    max-width: 360px;
    margin: auto;
    padding: 16px;
    text-align: center;
    color: var(--fg-2);
  }
  .icon {
    color: var(--fg-3);
    margin-block-end: 8px;
  }
  .title {
    font-size: 15px;
    line-height: 20px;
    font-weight: 600;
    color: var(--fg-1);
  }
  .text {
    font-size: var(--text-m);
    line-height: var(--line-m);
  }
  .action {
    margin-block-start: 8px;
    gap: 8px;
  }
</style>
