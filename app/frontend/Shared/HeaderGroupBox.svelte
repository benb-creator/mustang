<vbox class="group {classes}">
  <hbox class="header font-normal">
    <slot name="header" />
    <hbox flex />
    <hbox class="buttons">
      <slot name="buttons-top-right" />
    </hbox>
  </hbox>
  <vbox class="content" flex>
    <slot />
  </vbox>
</vbox>

<script lang="ts">
  export let classes = "";
</script>

<style>
  .group {
    border: 1px solid var(--border);
    border-radius: 6px;
    margin-block-start: 24px;
  }
  :global(.lookout) .group {
    border: none;
    border-radius: 0;
    margin-block-start: 8px;
  }
  .header {
    background-color: var(--headerbar-bg);
    color: var(--headerbar-fg);
    border-bottom: 1px solid var(--border);
    padding: 12px 20px;
    font-weight: 500;
    align-items: center;
  }
  :global(.lookout) .header {
    background-color: transparent;
    border-bottom: 1px solid var(--lo-divider);
    padding: 0 0 4px 0;
    font-weight: 600;
  }
  .content {
    background-color: var(--main-bg);
    color: var(--main-fg);
    padding: 24px 20px 16px 20px;
  }
  :global(.lookout) .content {
    padding: 8px 0 8px 44px;
  }
</style>
