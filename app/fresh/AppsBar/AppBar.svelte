<vbox class="app-bar" class:small={$appGlobal.isSmall} role="navigation" aria-label={$t`Apps`}>
  <vbox class="app-logo">
    <AppIcon icon={logo} size="22px" />
  </vbox>
  <vbox flex class="apps">
    {#each $mainApps.each as app}
      <AppButton selected={selectedApp == app} classes={app.id}
        on:click={() => catchErrors(() => onSelectApp(app))} >
        <hbox slot="icon" class="app-icon" title={$appGlobal.isSmall ? app.name : null}>
          <AppIcon icon={appIcons[app.id] ?? app.icon} size="20px" />
        </hbox>
        <hbox slot="label" class="label">
          {app.name}
        </hbox>
      </AppButton>
      <SubAppsList mainApp={app} bind:selectedApp />
    {/each}
    <vbox flex class="middle">
      <DemoBarMiddle />
    </vbox>
  </vbox>
  {#if $showDemoToggle}
    // #if [!WEBMAIL]
    <vbox class="demo-toggle">
      <DemoToggle />
    </vbox>
    // #endif
  {/if}
  {#if $showApps.includes(settingsMustangApp)}
    <AppButton selected={selectedApp == settingsMustangApp} classes="settings"
      on:click={() => catchErrors(() => onSelectApp(settingsMustangApp))} >
      <hbox slot="icon" class="app-icon" title={$appGlobal.isSmall ? settingsMustangApp.name : null}>
        <AppIcon icon={SettingsIcon} size="20px" />
      </hbox>
      <hbox slot="label" class="label">
        {settingsMustangApp.name}
      </hbox>
    </AppButton>
  {/if}
</vbox>

<script lang="ts">
  import type { MustangApp } from "../../frontend/AppsBar/MustangApp";
  import { openApp, showDemoToggle } from "../../frontend/AppsBar/selectedApp";
  import { settingsMustangApp } from "../../frontend/Settings/Window/SettingsMustangApp";
  import AppButton from "../../frontend/AppsBar/AppButton.svelte";
  import AppIcon from "../../frontend/AppsBar/AppIcon.svelte";
  import SubAppsList from "../../frontend/AppsBar/SubAppsList.svelte";
  import DemoToggle from "../../frontend/AppsBar/DemoToggle.svelte";
  import DemoBarMiddle from "../../frontend/AppsBar/DemoBarMiddle.svelte";
  import { appGlobal } from "../../logic/app";
  import logo from "../../frontend/asset/icon/general/logo.svg?raw";
  import MailIcon from "lucide-svelte/icons/mail";
  import CalendarIcon from "lucide-svelte/icons/calendar";
  import ContactsIcon from "lucide-svelte/icons/book-user";
  import ChatIcon from "lucide-svelte/icons/message-square";
  import MeetIcon from "lucide-svelte/icons/video";
  import FilesIcon from "lucide-svelte/icons/folder";
  import WebAppsIcon from "lucide-svelte/icons/layout-grid";
  import TopicIcon from "lucide-svelte/icons/network";
  import SettingsIcon from "lucide-svelte/icons/settings";
  import { catchErrors } from "../../frontend/Util/error";
  import { t } from "../../l10n/l10n";
  import type { Collection } from "svelte-collections";

  /* in/out */
  export let selectedApp: MustangApp;
  /* Which apps to show on the app bar
   * readonly */
  export let showApps: Collection<MustangApp>;

  $: mainApps = showApps.filterObservable(app => app != settingsMustangApp);

  const appIcons = {
    mail: MailIcon,
    calendar: CalendarIcon,
    contacts: ContactsIcon,
    chat: ChatIcon,
    meet: MeetIcon,
    files: FilesIcon,
    webapps: WebAppsIcon,
    topic: TopicIcon,
  };

  function onSelectApp(app: MustangApp) {
    openApp(app, app.windowParams);
  }
</script>

<style>
  .app-bar {
    flex: 0 0 auto;
    width: 68px;
    min-height: 0;
    background-color: var(--spine-bg);
    color: var(--spine-fg);
    padding-block-end: var(--space-1);
  }
  .app-bar.small {
    width: 52px;
  }
  .app-logo {
    height: var(--topbar-height);
    flex: 0 0 auto;
    align-items: center;
    justify-content: center;
    color: var(--spine-fg);
    app-region: drag;
  }
  .app-logo :global(svg) {
    opacity: 0.85;
  }
  .app-logo :global(.circle-bars),
  .app-logo :global(.horse) {
    fill: currentColor;
    stroke: currentColor;
  }
  .app-logo :global(.horse) {
    display: none;
  }
  :global(.fresh:not([dir="rtl"]):has(.window-header.mac:not(.os-rtl))) .app-logo :global(svg),
  :global(.fresh[dir="rtl"]:has(.window-header.mac.os-rtl)) .app-logo :global(svg) {
    display: none;
  }
  .app-icon :global(svg.lucide) {
    stroke-width: 1.8;
  }
  .apps {
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
  }
  .apps::-webkit-scrollbar {
    width: 0;
  }
  .middle {
    align-items: center;
  }
  .app-bar.small :global(.app-button) {
    height: 44px;
    margin-inline-start: var(--space-1);
  }
  .app-bar.small :global(.app-button .label) {
    display: none;
  }
</style>
