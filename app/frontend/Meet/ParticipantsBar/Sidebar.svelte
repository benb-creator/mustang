<vbox flex class="participants-sidebar">
  <Time {meeting} />
  <!--MeetingNotes {meeting} /-->
  <hbox class="participants-header">
    <hbox flex />
    <hbox class="number">{$participants.length} {$t`Participants`}</hbox>
    <hbox flex class="right">
      <ShowSpeaker bind:selected />
    </hbox>
  </hbox>
  <ParticipantsList {participants} invited={meeting.invited} bind:selected {userIsModerator} />
  <ParticipantSearch {meeting} bind:selected />
</vbox>

<script lang="ts">
  import type { MeetingParticipant } from "../../../logic/Meet/Participant";
  import type { VideoConfMeeting } from "../../../logic/Meet/VideoConfMeeting";
  import type { Collection } from "svelte-collections";
  import ParticipantsList from "./ParticipantsList.svelte";
  import ShowSpeaker from "./ShowSpeaker.svelte";
  import ParticipantSearch from "./ParticipantSearch.svelte";
  import Time from "./Time.svelte";
  import { t } from "../../../l10n/l10n";

  export let meeting: VideoConfMeeting;
  export let participants: Collection<MeetingParticipant>;
  export let selected: MeetingParticipant;
  export let userIsModerator = false;
</script>

<style>
  .participants-sidebar {
    background-color: #494558;
    color: white;
    box-shadow: 0px 4px 8px 0px rgba(0, 0, 0, 46%);
  }
  /** Override Contacts/Person/PersonsList.svelte */
  .participants-sidebar :global(.row.odd:not(.selected):not(:hover) hbox.person) {
    background-color: inherit; /*#403c4d;*/
    color: inherit;
  }
  .participants-header {
    align-items: center;
    margin-block-start: 12px;
  }
  .participants-header .right {
    align-items: center;
    justify-content: center;
  }
  :global(.fresh) .participants-sidebar {
    background-color: var(--l3-bg);
    color: var(--fg-1);
    box-shadow: none;
  }
  :global(.fresh) .participants-header {
    box-sizing: border-box;
    min-height: var(--pane-header-height);
    margin: 0;
    padding-inline: 16px;
    border-bottom: 1px solid var(--border-subtle);
  }
  :global(.fresh) .number {
    font-size: var(--text-xl);
    line-height: var(--line-xl);
    font-weight: 600;
    color: var(--fg-1);
  }
</style>
