<Clickable onClick={onClose}>
  <vbox class="app-menu" flex>
    <hbox class="date">
      {getFormattedDateString(new Date(), { weekday: "long", day: "numeric", month: "long" })}
    </hbox>
    <hbox flex />
    <!--<RecentPersons />-->
    <vbox class="apps" in:fly|global={{ y: 48, duration: reducedMotion ? 0 : 220, easing: cubicOut }}>
      <!--<WebAppsAppMenu />-->
      <FilesAppMenu />
      <CalendarAppMenu />
      <MeetAppMenu />
      <ChatAppMenu />
      <MailAppMenu />
      <ContactsAppMenu />
    </vbox>
  </vbox>
</Clickable>
<AppMenuBarM />

<script lang="ts">
  import { getFormattedDateString } from "../../../logic/util/date";
  import WebAppsAppMenu from "./Apps/WebAppsAppMenu.svelte";
  import FilesAppMenu from "./Apps/FilesAppMenu.svelte";
  import CalendarAppMenu from "./Apps/CalendarAppMenu.svelte";
  import MeetAppMenu from "./Apps/MeetAppMenu.svelte";
  import ChatAppMenu from "./Apps/ChatAppMenu.svelte";
  import MailAppMenu from "./Apps/MailAppMenu.svelte";
  import ContactsAppMenu from "./Apps/ContactsAppMenu.svelte";
  import AppMenuBarM from "./AppMenuBarM.svelte";
  import RecentPersons from "./RecentPersons.svelte";
  import Clickable from "../../Shared/Clickable.svelte";
  import { goBack } from "../selectedApp";
  import { fly } from "svelte/transition";
  import { cubicOut } from "svelte/easing";

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function onClose() {
    goBack();
  }
</script>

<style>
  :global(.content) .app-menu {
    background-color: transparent;
  }
  .app-menu {
    padding: 24px 12px 12px 12px;
  }
  .date {
    padding-inline: 12px;
    font-size: 24px;
    font-weight: 500;
  }
  .apps {
    gap: 4px;
  }
</style>
