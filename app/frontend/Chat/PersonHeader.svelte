<hbox class="person">
  <PersonPicture {person} />
  <vbox flex class="name-box">
    <hbox class="name">{$person.name}</hbox>
  </vbox>
  <hbox class="actions">
    {#if callTarget}
      <RoundButton label={$t`Video call`} icon={VideoCallIcon} classes="secondary large"
        onClick={() => startVideoCall(callTarget)} />
      <RoundButton label={$t`Audio call`} icon={VoiceCallIcon} classes="secondary large"
        onClick={() => startAudioCall(callTarget)} />
    {/if}
  </hbox>
  <hbox flex class="spacer" />
</hbox>

<script lang="ts">
  import { Person } from "../../logic/Abstract/Person";
  import { Group } from "../../logic/Abstract/Group";
  import { ChatPersonUID } from "../../logic/Chat/ChatPersonUID";
  import type { ChatContact } from "../../logic/Chat/ChatRoom";
  import { startVideoCall, startAudioCall } from "../../logic/Meet/StartCall";
  import PersonPicture from "../Contacts/Person/PersonPicture.svelte";
  import RoundButton from "../Shared/RoundButton.svelte";
  import VideoCallIcon from '../asset/icon/appBar/meet.svg?raw';
  import VoiceCallIcon from '../asset/icon/meet/callVoice.svg?raw';
  import { t } from "../../l10n/l10n";

  export let person: ChatContact | Person;

  /** Calls a real `Person`/`Group` for now.
   * TODO Later, we should prefer calling via Chat. */
  $: callTarget = person instanceof ChatPersonUID ? person.findPerson() : (person as Person | Group);
</script>

<style>
  .name-box {
    font-weight: bold;
    margin: 15px;
  }
  .actions {
    align-items: center;
  }
  .actions :global(button) {
    margin-inline-end: 8px;
  }
  :global(.fresh) .person {
    --person-picture-size: 32px;
    flex: none;
    align-items: center;
    gap: 12px;
    box-sizing: border-box;
    height: var(--pane-header-height);
    padding: 0 24px;
    border-bottom: 1px solid var(--border-subtle);
    background-color: var(--l3-bg);
  }
  :global(.fresh) .name-box {
    min-width: 0;
    margin: 0;
    font-size: var(--text-xl);
    line-height: var(--line-xl);
    font-weight: 600;
    color: var(--fg-1);
  }
  :global(.fresh) .name {
    display: block;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  :global(.fresh) .actions {
    gap: 4px;
  }
  :global(.fresh) .actions :global(.button.button) {
    min-width: var(--icon-button-size);
    min-height: var(--icon-button-size);
    margin: 0;
    border-color: transparent;
    background-color: transparent;
    color: var(--fg-2);
  }
  :global(.fresh) .actions :global(.button.button.border:hover:not(.disabled)) {
    border-color: transparent;
    background-color: transparent;
    color: var(--fg-1);
  }
  :global(.fresh) .actions :global(svg) {
    width: 16px;
    height: 16px;
  }
  :global(.fresh) .actions :global(svg path) {
    stroke: currentColor;
  }
  :global(.fresh) .spacer {
    display: none;
  }
</style>
