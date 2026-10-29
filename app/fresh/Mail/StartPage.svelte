<vbox class="mail-start-page" flex>
  {#if $selectedFolder}
    <EmptyState icon={logo} title={$selectedFolder.name}>
      <FolderMsgCount folder={$selectedFolder} searchMessages={null} />
    </EmptyState>
  {/if}
</vbox>

<script lang="ts">
  import { selectedFolder } from "../../frontend/Mail/Selected";
  import FolderMsgCount from "../../frontend/Mail/LeftPane/FolderMsgCount.svelte";
  import EmptyState from "../Shared/EmptyState.svelte";
  import logo from "../../frontend/asset/icon/general/logo.svg?raw";
</script>

<style>
  .mail-start-page {
    align-items: center;
    justify-content: center;
    background-color: var(--l3-bg);
  }
  .mail-start-page :global(.empty-state .icon) {
    opacity: 12%;
    color: var(--fg-1);
  }
  .mail-start-page :global(.empty-state .icon .circle-bars) {
    fill: currentColor;
    stroke: currentColor;
  }
  .mail-start-page :global(.empty-state .icon .horse) {
    display: none;
  }
  .mail-start-page :global(.empty-state .icon svg) {
    width: 64px;
    height: 64px;
  }
</style>
