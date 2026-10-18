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
    border-radius: var(--popup-radius);
    margin-block-start: 24px;
    overflow: hidden;
  }
  .header {
    background-color: var(--leftbar-bg);
    color: var(--leftbar-fg);
    border-bottom: 1px solid var(--border);
    padding: 10px 20px;
    font-weight: 600;
    align-items: center;
  }
  .content {
    background-color: var(--main-bg);
    color: var(--main-fg);
    padding: 24px 20px 16px 20px;
  }
</style>
