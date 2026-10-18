<hbox class="window-header" class:os-rtl={osRTL} class:mac
  style="--workspace-color: {$selectedWorkspace?.color ?? "var(--windowheader-bg)"}">
  <vbox class="app-logo">
    <Icon data={logo} size="20px" />
  </vbox>
  <hbox class="workspace">
    <WorkspaceHeader {selectedApp} />
  </hbox>
  <hbox class="app-title value">
    {$titleStore ?? selectedApp?.name ?? appName}
  </hbox>
  <vbox flex class="free" />
  <hbox class="search-box">
    <SearchField bind:searchTerm={$globalSearchTerm} />
  </hbox>
  <vbox flex class="free" />
  {#if !webMail}
    <hbox class="right">
      <Button label={$t`Minimize`}
        icon={MinimizeIcon} iconSize="16px" plain iconOnly classes="minimize"
        onClick={onMinimize}
        />
      <Button label={$t`Maximize`} tooltip={canMaximize ? $t`Maximize` : $t`Restore window`}
        icon={canMaximize ? MaximizeIcon : UnmaximizeIcon}
        iconSize="12px" plain iconOnly classes="restore-window"
        onClick={onMaximizeOrRestore}
        />
      <Button label={$t`Close entire app`}
        icon={XIcon} iconSize="16px" plain iconOnly classes="close"
        onClick={onCloseApp}
        />
    </hbox>
  {/if}
</hbox>

<script lang="ts">
  import type { MustangApp } from "../AppsBar/MustangApp";
  import { globalSearchTerm } from "../AppsBar/selectedApp";
  import { appGlobal } from "../../logic/app";
  import { appName, webMail } from "../../logic/build";
  import WorkspaceHeader from "./WorkspaceHeader.svelte";
  import SearchField from "../Shared/SearchField.svelte";
  import Button from "../Shared/Button.svelte";
  import Icon from 'svelte-icon/Icon.svelte';
  import logo from '../asset/icon/general/logo.svg?raw';
  import MinimizeIcon from 'lucide-svelte/icons/minus';
  import MaximizeIcon from 'lucide-svelte/icons/square';
  import UnmaximizeIcon from 'lucide-svelte/icons/copy';
  import XIcon from 'lucide-svelte/icons/x';
  import { getOSName } from "../Util/util";
  import { t } from "../../l10n/l10n";
  import { rtlLocales } from "../../l10n/list";
  import { selectedWorkspace } from "./Selected";

  export let selectedApp: MustangApp;

  // Enable Mac Styles
  const mac = (!webMail && getOSName() == "macintosh") ? true : false;
  // Check mac system text direction
  const osRTL = (rtlLocales.includes(navigator.language) && mac) ? true : false;

  function onMinimize() {
    appGlobal.remoteApp.minimizeMainWindow();
  }

  let canMaximize = true;
  function onMaximizeOrRestore() {
    if (canMaximize) {
      appGlobal.remoteApp.maximizeMainWindow();
    } else {
      appGlobal.remoteApp.unminimizeMainWindow();
    }
    canMaximize = !canMaximize;
  }

  function onCloseApp() {
    window.close();
  }

  $: titleStore = selectedApp?.title;
</script>

<style>
  .window-header {
    background-color: var(--windowheader-bg);
    color: var(--windowheader-fg);
    height: 40px;
    align-items: stretch;
    box-shadow: inset 0px -2px 0px 0px var(--workspace-color);
  }
  .app-logo {
    padding: 8px;
    padding-inline-start: 14px;
    width: 42px;
    align-items: start;
    justify-content: center;
    app-region: drag;
  }
  .workspace {
    align-items: center;
  }
  .app-title {
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.01em;
    align-items: center;
    margin-inline-start: 4px;
    app-region: drag;
  }
  .right {
    align-items: stretch;
  }
  .right :global(button) {
    color: var(--windowheader-fg);
    width: 46px;
    border-radius: 0px;
    opacity: 85%;
  }
  .right :global(button:hover) {
    background-color: rgba(255, 255, 255, 10%) !important;
    color: var(--windowheader-fg) !important;
    opacity: 100%;
  }
  .right :global(button.close:hover) {
    background-color: #C42B1C !important;
    color: white !important;
  }
  .right :global(.minimize svg) {
    margin-block-start: 8px; /* Find better icon */
  }
  .free {
    app-region: drag;
  }

  .search-box {
    align-items: center;
    width: 40%;
    max-width: 560px;
    min-width: 200px;
  }
  .window-header :global(.search) {
    flex: 1 0 0;
    border: none;
    background-color: rgba(255, 255, 255, 10%);
    color: var(--windowheader-fg);
    transition: background-color 80ms ease-out;
  }
  .window-header :global(.search:hover) {
    background-color: rgba(255, 255, 255, 15%);
  }
  .window-header :global(.search svg) {
    color: rgba(255, 255, 255, 65%);
  }
  .window-header :global(.search input::placeholder) {
    color: rgba(255, 255, 255, 60%);
  }
  .window-header :global(.search:has(input:focus)),
  .window-header :global(.search.has-search) {
    background-color: var(--bg);
    color: var(--fg);
    box-shadow: none;
  }
  .window-header :global(.search:has(input:focus) svg),
  .window-header :global(.search.has-search svg) {
    color: var(--fg-muted);
  }
  .window-header :global(.search:has(input:focus) input::placeholder),
  .window-header :global(.search.has-search input::placeholder) {
    color: var(--input-placeholder);
  }

  /* Styles for Mac */
  .mac .right {
    display: none;
  }
  .mac .app-logo,
  :global([dir="rtl"]) .mac.os-rtl .app-logo {
    margin-inline-start: 80px;
    width: 15px;
  }
  :global([dir="rtl"]) .mac:not(.os-rtl) .app-logo,
  .mac.os-rtl .app-logo {
    margin-inline-start: 0px;
  }
  :global([dir="rtl"]) .mac:not(.os-rtl) .search-box,
  .mac.os-rtl .search-box {
    padding-inline-end: 80px;
  }
  :global([dir="rtl"]) .mac .search-box {
    padding-inline-end: 0px;
  }
</style>
