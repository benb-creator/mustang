<GroupBox classes="person" headerName="">
  <hbox flex class="main-left" slot="content" language={getUILocale()}>
    <hbox flex class="identity">
      {#if $person.picture}
        <vbox class="picture">
          <PersonPicture {person} size={96} placeholder="empty" />
          {#if isEditing}
            <hbox class="picture-buttons">
              <Button
                label={$t`Delete picture`}
                onClick={deletePicture}
                icon={DeleteIcon}
                iconOnly plain classes="delete-picture" />
              <SetPictureButton {person} />
            </hbox>
          {/if}
        </vbox>
      {:else}
        <hbox class="no-avatar" />
      {/if}
      <vbox class="main-info">
        <hbox class="name">
          <EditableSimpleText bind:value={person.name}
            on:save={save}
            bind:isEditing
            isName={true}
            placeholder={$t`First name Last name`} />
        </hbox>
        {#if isEditing}
          <hbox class="two-fields">
            {#if !$person.picture}
              <SetPictureButton {person} />
            {/if}
            <hbox class="names firstname">
              <EditableSimpleText
                bind:value={person.firstName}
                on:save={save}
                bind:isEditing
                placeholder={$t`First name`} />
            </hbox>
            <hbox class="names lastname">
              <EditableSimpleText
                bind:value={person.lastName}
                on:save={save}
                bind:isEditing
                placeholder={$t`Last name`} />
            </hbox>
          </hbox>
        {/if}
        <vbox class="job-company">
          <hbox class="two-fields">
            {#if $person.position || isEditing}
              <hbox class="position">
                <EditableSimpleText
                  bind:value={person.position}
                  on:save={save}
                  bind:isEditing
                  placeholder={$t`Position`} />
              </hbox>
            {/if}
            {#if $person.department || isEditing}
              <hbox class="department">
                <EditableSimpleText
                  bind:value={person.department}
                  on:save={save}
                  bind:isEditing
                  placeholder={$t`Department`} />
              </hbox>
            {/if}
          </hbox>
          {#if $person.company || isEditing}
            <hbox class="company">
              <EditableSimpleText
                bind:value={person.company}
                on:save={save}
                bind:isEditing
                placeholder={$t`Company`} />
            </hbox>
          {/if}
        </vbox>
      </vbox>
    </hbox>
    <hbox flex class="main-right">
      <hbox class="call-buttons" class:editing={isEditing}>
        {#if isEditing}
          <RoundButton
            label={$t`Save`}
            onClick={save}
            icon={SaveIcon}
            iconSize="20px"
            classes="edit-save large secondary action"
            />
        {:else}
          <RoundButton
            label={$t`Edit`}
            onClick={() => isEditing = !isEditing}
            icon={PencilIcon}
            iconSize="20px"
            classes="edit-save large secondary action"
            />
        {/if}
        <CallButtons {person} />
      </hbox>
      <hbox flex class="spacer" />
      <hbox class="main-right-top">
        <AddressbookChanger {person} />
        <PersonMenu {person} />
      </hbox>
    </hbox>
  </hbox>
</GroupBox>

<script lang="ts">
  import type { Person } from "../../../logic/Abstract/Person";
  import { newPerson } from "../Person/Selected";
  import CallButtons from "./CallButtons.svelte";
  import EditableSimpleText from "./EditableSimpleText.svelte";
  import GroupBox from "./GroupBox.svelte";
  import PersonMenu from "./PersonMenu.svelte";
  import PersonPicture from "../Person/PersonPicture.svelte";
  import SetPictureButton from "./SetPictureButton.svelte";
  import AddressbookChanger from "../AddressbookChanger.svelte";
  import Button from "../../Shared/Button.svelte";
  import RoundButton from "../../Shared/RoundButton.svelte";
  import PencilIcon from "lucide-svelte/icons/pencil";
  import SaveIcon from "lucide-svelte/icons/save";
  import DeleteIcon from "lucide-svelte/icons/trash-2";
  import { showError } from "../../Util/error";
  import { getUILocale, t } from "../../../l10n/l10n";

  export let person: Person;
  /** in/out */
  export let isEditing: boolean;

  async function save() {
    try {
      await person.save();
      isEditing = false;
      $newPerson = null;
    } catch (ex) {
      showError(ex);
    }
  }

  function deletePicture() {
    person.picture = null;
  }
</script>

<style>
  .main-left {
    margin-inline-start: -16px;
    margin-inline-end: -8px;
    margin-block-end: -8px;
  }
  .main-info {
    margin-inline-start: 12px;
    margin-block-start: 4px;
    margin-block-end: 16px;
  }
  .picture {
    align-self: start;
    align-items: end; /* Below the avatar, at its right */
    margin-inline-end: 16px;
  }
  .picture-buttons {
    gap: 4px;
    margin-block-start: 2px;
  }
  .picture-buttons :global(button) {
    min-width: 0px;
    margin-block-start: 4px;
    padding: 3px;
    border: 1px solid var(--border);
    border-radius: 1000px;
    background-color: var(--main-bg);
  }
  .no-avatar {
    width: 16px; /* Room for the `SetPictureButton`, also outside of edit mode */
  }
  .two-fields :global(button.set-picture) {
    align-self: center;
    flex-shrink: 0; /* The name fields next to it are `width: 100%` */
    min-width: 0px;
    padding: 0px;
    margin-block-start: 9px; /* Same as the input, so that both are centered alike */
    margin-inline-start: -24px; /* Align with the icon of the mail group below */
    margin-inline-end: 8px;
  }
  .name,
  .name :global(input) {
    font-size: 18px;
    font-weight: bold;
    margin-block-end: 8px;
    color: inherit;
  }
  .name :global(input) {
    width: 20em;
  }
  .names :global(button.save),
  .job-company :global(button.save) {
    visibility: hidden;
  }
  .main-left[language="fr"] .names.lastname {
    text-transform: uppercase;
  }
  .two-fields > hbox {
    width: 100%;
  }
  .job-company {
    color: grey;
  }
  .job-company :global(.actions),
  .job-company :global(.value) {
    margin-block-start: 2px;
  }
  .main-right {
    margin: 8px;
    flex-wrap: wrap;
  }
  .main-right-top {
    justify-content: end;
    align-items: start;
    margin-block-start: px;
  }
  .main-right-top :global(.account-selector .icon) {
    width: 20px;
    height: 20px;
  }
  .call-buttons {
    align-items: center;
    gap: 10px;
  }
  .call-buttons :global(.edit-save svg) {
    stroke-width: 1.5px;
  }

  :global(.fresh) .main-left {
    align-items: center;
    gap: 16px;
    margin: 0;
  }
  :global(.fresh) .identity {
    align-items: center;
    gap: 16px;
    min-width: 0;
  }
  :global(.fresh) .picture {
    --person-picture-size: 72px;
    align-self: center;
    align-items: center;
    margin: 0;
  }
  :global(.fresh) .picture-buttons {
    margin-block-start: 6px;
  }
  :global(.fresh) .picture-buttons :global(button) {
    margin: 0;
    padding: 0;
    border: 1px solid var(--border-control);
    border-radius: var(--radius-m);
    background-color: var(--btn-sec-bg);
  }
  :global(.fresh) .no-avatar {
    width: 0;
  }
  :global(.fresh) .main-info {
    justify-content: center;
    gap: 4px;
    min-width: 0;
    margin: 0;
  }
  :global(.fresh) .name,
  :global(.fresh) .name :global(input) {
    margin: 0;
    font-size: var(--text-3xl);
    line-height: var(--line-3xl);
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--fg-1);
  }
  :global(.fresh) .name :global(input) {
    box-sizing: border-box;
    width: 20em;
    max-width: 100%;
    height: var(--control-height-l);
    font-size: var(--text-2xl);
    line-height: var(--line-2xl);
  }
  :global(.fresh) .two-fields {
    gap: 8px;
  }
  :global(.fresh) .two-fields :global(button.set-picture) {
    margin: 0;
  }
  :global(.fresh) .job-company {
    gap: 4px;
    font-size: var(--text-l);
    line-height: var(--line-l);
    color: var(--fg-2);
  }
  :global(.fresh) .job-company:not(:has(input)) {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0;
  }
  :global(.fresh) .job-company:not(:has(input)) .two-fields {
    gap: 0;
  }
  :global(.fresh) .job-company:not(:has(input)) .two-fields > hbox {
    width: auto;
  }
  :global(.fresh) .job-company:not(:has(input)) .two-fields > hbox + hbox::before,
  :global(.fresh) .job-company:not(:has(input)) .two-fields:has(> hbox) + .company::before {
    content: "·";
    margin-inline: 6px;
  }
  :global(.fresh) .job-company :global(.value) {
    margin: 0;
  }
  :global(.fresh) .main-right {
    flex: 0 1 auto;
    flex-wrap: nowrap;
    align-items: center;
    gap: 4px;
    margin: 0;
  }
  :global(.fresh) .spacer {
    display: none;
  }
  :global(.fresh) .main-right-top {
    align-items: center;
    gap: 4px;
  }
  :global(.fresh) .call-buttons {
    gap: 4px;
  }
  :global(.fresh) .call-buttons :global(.button.button) {
    min-width: var(--icon-button-size);
    min-height: var(--icon-button-size);
    border-color: transparent;
    background-color: transparent;
    color: var(--fg-2);
  }
  :global(.fresh) .call-buttons :global(.button.button.border:hover:not(.disabled)) {
    border-color: transparent;
    background-color: transparent;
    color: var(--fg-1);
  }
  :global(.fresh) .call-buttons :global(.button svg) {
    width: 16px;
    height: 16px;
  }
  :global(.fresh) .call-buttons.editing :global(.button.button.edit-save) {
    border-color: var(--accent);
    background-color: var(--accent);
    color: var(--fg-on-accent);
  }
  :global(.fresh) .call-buttons.editing :global(.button.button.edit-save:hover:not(.disabled)) {
    border-color: var(--accent-hover);
    background-color: var(--accent-hover);
    background-image: none;
    color: var(--fg-on-accent);
  }
  @container (max-width: 640px) {
    :global(.fresh) .main-left {
      flex-wrap: wrap;
      gap: 8px;
    }
    :global(.fresh) .identity {
      flex: 1 1 100%;
    }
    :global(.fresh) .main-right {
      flex: 1 1 100%;
    }
  }
</style>
