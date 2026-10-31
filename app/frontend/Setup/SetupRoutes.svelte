<div class="setup-routes">
  <Route path="initial">
    <InitialSetup />
  </Route>
  <Route path="predefined">
    <SetupPredefinedMail account={params.account} />
  </Route>
  <Route path="mail">
    <SetupMail />
  </Route>
  <Route path="chat">
    <SetupChat />
  </Route>
  <Route path="contacts">
    <SetupContacts />
  </Route>
  <Route path="calendar">
    <SetupCalendar />
  </Route>
  <Route path="meet">
    <SetupMeetAccount />
  </Route>
  <Route path="files">
    <SetupFiles />
  </Route>
  <Route path="/">
    <SetupAnyAccountTypeDialog />
  </Route>
</div>

<script lang="ts">
  import InitialSetup from "./Import/InitialSetup.svelte";
  import SetupAnyAccountTypeDialog from "./SetupAnyAccountTypeDialog.svelte";
  import SetupMail from "./Mail/SetupMail.svelte";
  import SetupPredefinedMail from "./Mail/SetupPredefinedMail.svelte";
  import SetupChat from "./Chat/SetupChat.svelte";
  import SetupContacts from "./Contacts/SetupContacts.svelte";
  import SetupCalendar from "./Calendar/SetupCalendar.svelte";
  import SetupMeetAccount from "./Meet/SetupMeetAccount.svelte";
  import SetupFiles from "./Files/SetupFiles.svelte";
  import { Route, useLocation } from "svelte-navigator";
  import { getParams } from "../AppsBar/selectedApp";

  $: location = useLocation();
  $: params = getParams($location?.state);
</script>

<style>
  .setup-routes {
    display: contents;
  }
  :global(.mobile) .setup-routes :global(:has(> .page-box)) {
    position: relative;
  }
  :global(.mobile) .setup-routes :global(.page-box) {
    position: absolute;
    inset: min(22%, 180px) 0px 0px 0px;
    max-width: none;
    padding: 28px 16px 16px 16px;
    border-radius: 24px 24px 0px 0px;
    box-shadow: 0px -2px 12px rgba(0, 0, 0, 15%);
    overflow-y: auto;
    overscroll-behavior: contain;
    animation: sheet-up 260ms cubic-bezier(0.2, 0.9, 0.3, 1) both;
  }
  :global(.mobile) .setup-routes :global(input:is([type="text"], [type="email"], [type="url"], [type="number"], [type="password"], [type="tel"])),
  :global(.mobile) .setup-routes :global(select) {
    min-height: 44px;
    font-size: 16px;
  }
  :global(.mobile) .setup-routes :global(input:is([type="checkbox"], [type="radio"])) {
    flex: none;
    width: 22px;
    height: 22px;
  }
  :global(.mobile) .setup-routes :global(label:has(> input:is([type="checkbox"], [type="radio"]))) {
    display: flex;
    align-items: center;
    min-height: 48px;
  }
  :global(.mobile) .setup-routes :global(grid.fields) {
    grid-template-columns: minmax(0, 1fr);
    gap: 4px;
    margin: 0px;
  }
  :global(.mobile) .setup-routes :global(grid.fields > label:not(:first-child)) {
    margin-block-start: 12px;
  }
  @keyframes sheet-up {
    from {
      transform: translateY(48px);
      opacity: 0;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    :global(.mobile) .setup-routes :global(.page-box) {
      animation: none;
    }
  }
</style>
