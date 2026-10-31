<AppMenuRow app={meetMustangApp} page="/meet/">
  <hbox class="empty" />
  <BasicButton icon={HistoryIcon} page="/meet/history" />
  <BasicButton icon={PlusIcon} onClick={onCreateMeeting} />
  <CombinedButton slot="person"
    icon1={meetMustangApp.icon}
    icon2={$selectedPerson?.picture ?? PersonIcon}
    onClick={() => onCallPerson($selectedPerson)} />
</AppMenuRow>

<script lang="ts">
  import { meetMustangApp } from "../../../Meet/MeetMustangApp";
  import { startAdHocMeeting, callSelected } from "../../../Meet/Start/start";
  import { goTo, openApp } from "../../selectedApp";
  import AppMenuRow from "../AppMenuRow.svelte";
  import CombinedButton from "../CombinedButton.svelte";
  import BasicButton from "../BasicButton.svelte";
  import HistoryIcon from "lucide-svelte/icons/history";
  import PersonIcon from "lucide-svelte/icons/user";
  import PlusIcon from "lucide-svelte/icons/plus";
  import { selectedPerson } from "../../../Contacts/Person/Selected";
  import { Person } from "../../../../logic/Abstract/Person";

  async function onCreateMeeting() {
    let meeting = await startAdHocMeeting();
    openApp(meetMustangApp, { meeting });
  }

  async function onCallPerson(person: Person) {
    let meeting = await callSelected(person);
    goTo("/meet/call", { meeting });
  }
</script>
