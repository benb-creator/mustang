<vbox class="settings-panel" flex>
  <slot />
</vbox>

<script lang="ts">
  /** Shows the settings pages, which were made for the desktop window, as phone forms */
</script>

<style>
  .settings-panel {
    padding: 0px 16px 32px 16px;
    overflow-wrap: normal;
  }
  .settings-panel :global(.group) {
    margin-inline: -16px;
  }
  .settings-panel :global(input:is([type="text"], [type="email"], [type="url"], [type="number"], [type="password"], [type="tel"], [type="search"])),
  .settings-panel :global(select) {
    min-height: 44px;
    font-size: 16px;
  }
  .settings-panel :global(textarea) {
    font-size: 16px;
  }
  .settings-panel :global(input:is([type="checkbox"], [type="radio"])) {
    flex: none;
    width: 22px;
    height: 22px;
  }
  .settings-panel :global(label:has(> input:is([type="checkbox"], [type="radio"]))) {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
  }
  .settings-panel :global(button.button) {
    min-width: 44px;
    min-height: 44px;
  }
  .settings-panel :global(button.button svg) {
    min-width: 18px;
    min-height: 18px;
  }
  .settings-panel :global(grid.fields) {
    grid-template-columns: minmax(0, 1fr);
    gap: 4px;
  }
  .settings-panel :global(grid.fields > label:not(:first-child)) {
    margin-block-start: 12px;
  }
  .settings-panel :global(h2) {
    margin: 0px;
    font-size: 22px;
  }
  .settings-panel :global(h2 + .subtitle) {
    padding-block-start: 4px;
    opacity: 75%;
  }
</style>
