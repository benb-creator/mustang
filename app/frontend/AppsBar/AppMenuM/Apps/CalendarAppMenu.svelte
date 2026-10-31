<AppMenuRow app={calendarMustangApp} page="/calendar/">
  <BasicButton label={$t`TODO`} icon={TODOsIcon} onClick={goToTODOs} />
  <BasicButton icon={SearchIcon} page="/calendar/search" />
  <BasicButton icon={PlusIcon} onClick={onCreateEvent} />
  <CombinedButton slot="person"
    icon1={calendarMustangApp.icon}
    icon2={$selectedPerson?.picture ?? PersonIcon}
    page="/calendar/person"
    params={{ person: $selectedPerson}} />
</AppMenuRow>

<script lang="ts">
  import { setNewEventTime } from "../../../Calendar/event";
  import { calendarMustangApp } from "../../../Calendar/CalendarMustangApp";
  import { openEvent } from "../../../Calendar/open";
  import { selectedCalendar } from "../../../Calendar/selected";
  import { selectedPerson } from "../../../Contacts/Person/Selected";
  import { appGlobal } from "../../../../logic/app";
  import { goTo } from "../../selectedApp";
  import AppMenuRow from "../AppMenuRow.svelte";
  import CombinedButton from "../CombinedButton.svelte";
  import BasicButton from "../BasicButton.svelte";
  import SearchIcon from "lucide-svelte/icons/search";
  import PersonIcon from "lucide-svelte/icons/user";
  import PlusIcon from "lucide-svelte/icons/plus";
  import TODOsIcon from "lucide-svelte/icons/square-check-big";
  import { assert } from "../../../../logic/util/util";
  import { t } from "../../../../l10n/l10n";

  function onCreateEvent() {
    let calendar = $selectedCalendar ?? appGlobal.calendars.first;
    assert(calendar, "Create a calendar first");
    let event = calendar.newEvent();
    setNewEventTime(event, false, new Date());
    openEvent(event);
  }

  function goToTODOs() {
    goTo("/calendar/todos", {});
  }
</script>
