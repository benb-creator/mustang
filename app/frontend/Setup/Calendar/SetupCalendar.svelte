<vbox flex class="setup-calendar-window">
  <hbox flex />
  <vbox class="page-box">
    <svelte:component this={showPage} bind:showPage bind:config
      onCancel={onClose}
      />
  </vbox>
  <hbox flex />
  <BackgroundVideo />
</vbox>

<script lang="ts">
  import type { Calendar } from "../../../logic/Calendar/Calendar";
  import { selectedApp } from "../../AppsBar/selectedApp";
  import { openSettingsCategoryForApp } from "../../Settings/Window/CategoriesUtils";
  import { calendarMustangApp } from "../../Calendar/CalendarMustangApp";
  import { SetupMustangApp } from "../SetupMustangApp";
  import SelectProtocol from "./SelectProtocol.svelte";
  import BackgroundVideo from "../Shared/BackgroundVideo.svelte";

  let config: Calendar;
  let showPage: ConstructorOfATypedSvelteComponent | null = SelectProtocol;

  $: checkClose(showPage);
  function checkClose(_dummy: any) {
    if (showPage) {
      return;
    }
    onClose();
  }

  function onClose() {
    if ($selectedApp instanceof SetupMustangApp && typeof($selectedApp.onBack) == "function") {
      $selectedApp.onBack();
    } else {
      openSettingsCategoryForApp(calendarMustangApp);
    }
  }
</script>

<style>
  .setup-calendar-window {
    justify-content: center;
    align-items: center;
  }
  .page-box {
    max-width: 32em;
    padding: 24px 48px 20px 48px;
    background-color: var(--main-bg);
    color: var(--main-fg);
  }
  :global(.mobile) .page-box {
    padding: 12px 24px;
  }
  .setup-calendar-window :global(input) {
    font-size: 16px;
  }
  .setup-calendar-window :global(input::placeholder) {
    font-weight: 300;
  }
  :global(.fresh) .setup-calendar-window {
    min-height: 0;
    overflow-y: auto;
    padding: 24px;
  }
  :global(.fresh) .page-box {
    flex: none;
    box-sizing: border-box;
    width: 560px;
    max-width: 100%;
    padding: 32px 40px 24px;
    border-radius: var(--radius-l);
    background-color: var(--l3-bg);
    color: var(--l3-fg);
    box-shadow: var(--shadow-pop);
    font-size: var(--text-l);
    line-height: var(--line-l);
  }
  :global(.fresh) .setup-calendar-window :global(input) {
    font-size: var(--text-l);
  }
  :global(.fresh) .setup-calendar-window :global(input::placeholder) {
    font-weight: 400;
  }
</style>
