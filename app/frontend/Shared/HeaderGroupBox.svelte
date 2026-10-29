<vbox class="group {classes}">
  <hbox class="header font-normal">
    <slot name="header" />
    <hbox flex class="rule" />
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
    border: var(--group-box-border);
    border-radius: var(--group-box-radius);
    margin-block-start: var(--group-box-margin-top);
  }
  .header {
    background-color: var(--group-box-header-bg);
    color: var(--headerbar-fg);
    border-bottom: var(--group-box-header-border);
    padding: var(--group-box-header-padding);
    font-weight: var(--group-box-header-weight);
    align-items: center;
  }
  .content {
    background-color: var(--main-bg);
    color: var(--main-fg);
    padding: var(--group-box-content-padding);
  }
  :global(.fresh) .group {
    border: none;
    border-radius: 0;
    margin-block-start: 24px;
  }
  :global(.fresh) .header {
    gap: 8px;
    min-height: var(--section-header-height);
    padding: 0;
    border-bottom: none;
    background-color: transparent;
    color: var(--fg-2);
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-weight: 600;
  }
  :global(.fresh) .header > .rule {
    align-self: center;
    min-width: 8px;
    height: 1px;
    background-color: var(--border-subtle);
  }
  :global(.fresh) .content {
    padding: 12px 0 8px;
    background-color: transparent;
    color: var(--fg-1);
  }
</style>
