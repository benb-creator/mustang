<vbox flex class="main-window desktop fresh" dir={rtl}>
  {#if $selectedWorkspace}
    <hbox class="workspace-band" style="background-color: {$selectedWorkspace.color}" />
  {/if}
  <hbox flex class="window-body">
    <AppBar bind:selectedApp={$selectedApp} showApps={mustangApps} />
    <vbox flex class="app-area">
      <WindowHeader selectedApp={$selectedApp} />
      <NotificationBar notifications={$notifications} />
      {#if $selectedApp}
        <RouterWithContent primary={false} {history}>
          <Splitter name="sidebar" initialRightRatio={0.25} hasRight={!!sidebar}>
            <AppContentRoutes slot="left" />
            <vbox flex class="sidebar" slot="right">
              <svelte:component this={sidebar} />
            </vbox>
          </Splitter>
        </RouterWithContent>
      {/if}
    </vbox>
  </hbox>
</vbox>

<script lang="ts">
  import freshCSS from "../app.css?inline";
  import freshContentCSS from "../Mail/Message/content.css?inline";
  import { selectedApp, mustangApps, history } from "../../frontend/AppsBar/selectedApp";
  import { notifications } from "../../logic/util/Notification";
  import { selectedWorkspace } from "../../frontend/MainWindow/Selected";
  import WindowHeader from "../../frontend/MainWindow/WindowHeader.svelte";
  import NotificationBar from "../../frontend/MainWindow/NotificationBar.svelte";
  import { contentStyle } from "../../frontend/Mail/Message/contentStyle";
  import AppBar from "../../frontend/AppsBar/AppBar.svelte";
  import AppContentRoutes from "../../frontend/AppsBar/AppContentRoutes.svelte";
  import Splitter from "../../frontend/Shared/Splitter.svelte";
  import { Router } from "svelte-navigator";
  import type { RouterProps } from "svelte-navigator/types/Router";
  import { onDestroy, type Component, type Snippet } from "svelte";

  /** The Meet sidebar, while a meeting is open */
  export let sidebar: ConstructorOfATypedSvelteComponent | null = null;
  export let rtl: string = null;

  /* <copied from="../../lookout/MainWindow/MainWindow.svelte"> */
  // Not a plain CSS import: the global CSS must go away when the user switches to another frontend at runtime
  const globalStyle = document.createElement("style");
  globalStyle.textContent = freshCSS;
  document.head.append(globalStyle);
  onDestroy(() => globalStyle.remove());

  // svelte-navigator's types don't declare the default slot, so svelte-check rejects any content
  const RouterWithContent = Router as unknown as Component<RouterProps & { children: Snippet }>;
  /* </copied> */

  $contentStyle = freshContentCSS;
  onDestroy(() => $contentStyle = "");
</script>

<style>
  .fresh {
    min-width: 640px;
    min-height: 0;
    overflow: hidden;
    background-color: var(--l1-bg);
    color: var(--fg-1);
    font-family: var(--font);
    font-size: var(--text-m);
    line-height: var(--line-m);
  }
  .workspace-band {
    flex: 0 0 3px;
  }
  .window-body {
    min-height: 0;
  }
  .app-area {
    min-width: 0;
    min-height: 0;
    container: app / inline-size;
  }
  .sidebar {
    border-inline-start: 1px solid var(--border);
    background-color: var(--l3-bg);
    color: var(--l3-fg);
  }
</style>
