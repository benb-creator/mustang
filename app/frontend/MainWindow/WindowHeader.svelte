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
  }
  .app-logo {
    padding: 8px;
    padding-inline-start: 12px;
    width: 48px;
    align-items: start;
    justify-content: center;
    app-region: drag;
  }
  .app-title {
    font-size: 18px;
    align-items: center;
    margin-inline-start: 4px;
    app-region: drag;
  }
  .right {
    padding-inline-end: 8px;
  }
  .right :global(button) {
    color: white;
    padding-inline-start: 8px;
    padding-inline-end: 8px;
  }
  .right :global(.maximize) {
    padding-inline-start: 10px;
    padding-inline-end: 10px;
  }
  .right :global(.minimize svg) {
    margin-block-start: 8px; /* Find better icon */
  }
  .free {
    app-region: drag;
  }

  .window-header :global(.search) {
    margin: 6px 12px;
    outline: 1px solid rgb(255, 255, 255, 7%);
    border: none;
  }
  .window-header :global(.search:not(.has-search)) {
    background-color: var(--windowheader-bg);
    /*background-color: rgb(255, 255, 255, 10%);
    background-blend-mode: multiply;*/
  }
  .window-header :global(.search :has(input:focus)) {
    background-color: var(--inverted-bg);
  }
  .window-header :global(.search:not(.has-search) input) {
    background-color: transparent;
    color: var(--inverted-fg);
  }

  .search-box {
    --gradient-direction: 135deg;
    background-image: linear-gradient(var(--gradient-direction), var(--windowheader-bg) 10%, var(--workspace-color) 85%);
  }
  :global([dir="rtl"]) .search-box {
    --gradient-direction: 225deg;
  }
  .right {
    background-color: var(--workspace-color);
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
  :global(.fresh) .window-header {
    flex: 0 0 auto;
    height: var(--topbar-height);
    box-sizing: border-box;
    align-items: center;
    padding-inline-start: var(--space-4);
    background-color: var(--l1-bg);
    color: var(--l1-fg);
    container: topbar / inline-size;
  }
  :global(.fresh:not([dir="rtl"])) .window-header.mac.os-rtl,
  :global(.fresh[dir="rtl"]) .window-header.mac:not(.os-rtl) {
    padding-inline-end: 80px;
  }
  :global(.fresh) .app-logo {
    display: none;
  }
  :global(.fresh) .app-title {
    order: 1;
    flex: 0 1 auto;
    min-width: 0;
    margin: 0;
    padding-inline-end: var(--space-4);
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-size: var(--text-xl);
    line-height: var(--line-xl);
    font-weight: 600;
    color: inherit;
  }
  :global(.fresh) .search-box {
    order: 2;
    flex: 0 1 360px;
    min-width: 160px;
    padding: 0;
    background-image: none;
  }
  @container topbar (min-width: 1280px) {
    :global(.fresh) .search-box {
      flex-basis: 480px;
    }
  }
  :global(.fresh) .free {
    order: 3;
    align-self: stretch;
  }
  :global(.fresh) .workspace {
    order: 4;
  }
  :global(.fresh) .right {
    order: 5;
    align-self: stretch;
    padding: 0;
    margin-inline-start: var(--space-2);
    background-color: transparent;
  }
  :global(.fresh) .window-header :global(.search) {
    flex: 1 1 auto;
    box-sizing: border-box;
    height: 32px;
    margin: 0;
    padding-inline-start: 10px;
    border: 1px solid var(--border-control);
    border-radius: var(--radius-m);
    outline: none;
    background-color: var(--input-bg);
    color: var(--fg-1);
  }
  :global(.fresh) .window-header :global(.search:has(input:focus)) {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }
  :global(.fresh) .window-header :global(.search input),
  :global(.fresh) .window-header :global(.search:not(.has-search) input) {
    background-color: transparent;
    color: var(--fg-1);
    font-size: var(--text-m);
  }
  :global(.fresh) .window-header :global(.search svg) {
    color: var(--fg-3);
  }
  :global(.fresh) .window-header .right :global(.button.plain.icon-only) {
    width: 44px;
    height: 100%;
    min-height: 0;
    padding: 0;
    margin: 0;
    border: none;
    border-radius: 0;
    background-color: transparent;
    background-image: none;
    color: inherit;
  }
  :global(.fresh) .window-header .right :global(.button.plain.icon-only:hover:not(.disabled)) {
    background-color: transparent;
    background-image: linear-gradient(var(--row-hover), var(--row-hover));
    color: inherit;
  }
  :global(.fresh) .window-header .right :global(.button.plain.icon-only.close:hover:not(.disabled)) {
    background-color: var(--danger);
    background-image: none;
    color: var(--fg-on-accent);
  }
  :global(.fresh) .window-header .right :global(.minimize svg) {
    margin-block-start: 0;
  }
</style>
