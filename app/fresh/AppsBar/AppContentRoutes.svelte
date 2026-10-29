<AppContentRoutes>
  <MailRoutes slot="mail" />
  <ChatRoutes slot="chat" />
  <ContactsRoutes slot="contacts" />
  <CalendarRoutes slot="calendar" />
  <FilesRoutes slot="files" />
  <SettingsRoutes slot="settings" />
  <TopicRoutes slot="topic">
    <TopicApp initialRightRatio={4} />
  </TopicRoutes>
  <hbox class="ring" slot="setup-background">
    <AppIcon icon={logo} size="480px" />
  </hbox>
</AppContentRoutes>

<script lang="ts">
  import AppContentRoutes from "../../frontend/AppsBar/AppContentRoutes.svelte";
  import MailRoutes from "../Mail/MailRoutes.svelte";
  import ChatRoutes from "../Chat/ChatRoutes.svelte";
  import ContactsRoutes from "../Contacts/ContactsRoutes.svelte";
  import CalendarRoutes from "../Calendar/CalendarRoutes.svelte";
  import FilesRoutes from "../Files/FilesRoutes.svelte";
  import SettingsRoutes from "../Settings/SettingsRoutes.svelte";
  import TopicRoutes from "../../frontend/Topic/TopicRoutes.svelte";
  import TopicApp from "../../frontend/Topic/TopicApp.svelte";
  import AppIcon from "../../frontend/AppsBar/AppIcon.svelte";
  import logo from "../../frontend/asset/icon/general/logo.svg?raw";
</script>

<style>
  .ring {
    position: absolute;
    inset: 0;
    z-index: -1;
    overflow: hidden;
    color: var(--fg-1);
    opacity: 0.06;
    pointer-events: none;
  }
  .ring :global(svg) {
    position: absolute;
    top: calc(50% + 120px);
    left: 50%;
    transform: translate(-50%, -50%);
  }
  .ring :global(.circle-bars) {
    fill: currentColor;
    stroke: currentColor;
  }
  .ring :global(.horse) {
    display: none;
  }
</style>
