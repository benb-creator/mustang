<!-- <copied to="../../lookout/AppsBar/AppContentRoutes.svelte"> -->
<vbox flex class="app-frame">
  <Route path="mail/*">
    <slot name="mail">
      <MailAppRoutes />
    </slot>
  </Route>
  <Route path="chat/*">
    <slot name="chat">
      <ChatRoutes />
    </slot>
  </Route>
  <Route path="contacts/*">
    <slot name="contacts">
      <ContactsAppRoutes />
    </slot>
  </Route>
  <Route path="calendar/*">
    <slot name="calendar">
      <CalendarRoutes />
    </slot>
  </Route>
  <Route path="files/*">
    <slot name="files">
      <FilesAppRoutes />
    </slot>
  </Route>
  <Route path="meet/*">
    <vbox flex class="page">
      <MeetAppRoutes />
    </vbox>
  </Route>
  <Route path="topic/*">
    <vbox flex class="page">
      <slot name="topic">
        <TopicRoutes />
      </slot>
    </vbox>
  </Route>
  <Route path="webapp/*">
    <vbox flex class="page">
      <WebAppsRoutes />
    </vbox>
  </Route>
  <Route path="settings/*">
    <slot name="settings">
      <SettingsRoutes />
    </slot>
  </Route>
  // #if [!WEBMAIL]
  <Route path="setup/*">
    <vbox flex class="setup-canvas">
      <slot name="setup-background" />
      <SetupRoutes />
    </vbox>
  </Route>
  // #endif
  <Route path="login/">
    <vbox flex class="page">
      <OAuth2EmbeddedBrowser dialog={params?.dialog ?? requiredParam()} />
    </vbox>
  </Route>
  <Route path="app-menu/">
    <vbox flex class="page">
      <AppMenu />
    </vbox>
  </Route>
  <Route path="/">
    <!-- default, on app start-->
    <slot name="mail">
      <MailAppRoutes />
    </slot>
  </Route>
</vbox>
<!-- </copied> -->

<script lang="ts">
  import AppMenu from "./AppMenuM/AppMenu.svelte";
  import MailAppRoutes from "../Mail/MailRoutes.svelte";
  import ChatRoutes from "../Chat/ChatRoutes.svelte";
  import ContactsAppRoutes from "../Contacts/ContactsRoutes.svelte";
  import FilesAppRoutes from "../Files/FilesRoutes.svelte";
  import CalendarRoutes from "../Calendar/CalendarRoutes.svelte";
  import MeetAppRoutes from "../Meet/MeetRoutes.svelte";
  import TopicRoutes from "../Topic/TopicRoutes.svelte";
  import WebAppsRoutes from "../WebApps/WebAppsRoutes.svelte";
  import SettingsRoutes from "../Settings/SettingsRoutes.svelte";
  // #if [!WEBMAIL]
  import SetupRoutes from "../Setup/SetupRoutes.svelte";
  // #endif
  import OAuth2EmbeddedBrowser from "../Shared/Auth/OAuth2EmbeddedBrowser.svelte";
  import { getParams } from "./selectedApp";
  import { requiredParam } from "../Util/route";
  import { Route, useLocation } from "svelte-navigator";

  /* <copied to="../../lookout/AppsBar/AppContentRoutes.svelte"> */
  $: location = useLocation();
  $: params = getParams($location?.state);
  /* </copied> */
</script>

<style>
  .page,
  .setup-canvas {
    display: contents;
  }
  :global(.fresh) .app-frame {
    min-width: 0;
    min-height: 0;
  }
  :global(.fresh) .page {
    display: flex;
    min-width: 0;
    min-height: 0;
    border-block-start: 1px solid var(--border);
    background-color: var(--l3-bg);
    color: var(--l3-fg);
  }
  :global(.fresh) .setup-canvas {
    display: flex;
    position: relative;
    isolation: isolate;
    min-width: 0;
    min-height: 0;
    background-color: var(--l1-bg);
  }
</style>
