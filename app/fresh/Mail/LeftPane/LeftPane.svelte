<LeftPane {accounts} {folders}
  bind:searchMessages bind:selectedAccount bind:selectedFolder bind:selectedFolders bind:activeTab
  let:showPerson let:endSearchMode let:onFolderSettings>
  <vbox flex class="folder-pane">
    <PaneHeader level="l1">
      <WriteButton account={selectedAccount}
        to={activeTab == SearchView.Person && $selectedPerson ? PersonUID.fromPerson($selectedPerson) : null } />
      <svelte:fragment slot="actions">
        {#if activeTab == SearchView.Folder}
          <GetMailButton folder={selectedFolder ?? selectedAccount?.inbox} />
        {/if}
      </svelte:fragment>
    </PaneHeader>
    <hbox class="mode-switcher">
      <SearchSwitcher bind:active={activeTab} />
    </hbox>

    {#if activeTab == SearchView.Person}
      <vbox flex class="persons" class:show-addressbook={$addressbooks.length > 1}>
        <PersonsList
          persons={appGlobal.persons}
          bind:selected={$selectedPerson}
          selectedPersons={new ArrayColl()}
          on:selected={ev => showPerson(ev.detail as Person)}
          />
      </vbox>
      <hbox class="footer">
        <ViewSwitcher />
      </hbox>
    {:else if activeTab == SearchView.Search}
      <SearchPane bind:searchMessages on:clear={endSearchMode} />
    {:else}
      <AccountList {accounts} bind:selectedAccount>
        <FolderList slot="folders" {folders} bind:selectedFolder bind:selectedFolders>
          <svelte:fragment slot="buttons" let:folder>
            <GetMailButton {folder} />
            <Button label={$t`Folder properties`} icon={MoreIcon} iconOnly plain classes="small"
              onClick={() => onFolderSettings(folder)} />
          </svelte:fragment>
        </FolderList>
      </AccountList>
      {#if selectedFolder && !(selectedFolder instanceof SavedSearchFolder)}
        <vbox class="tags">
          {#if $availableTags.hasItems}
            <SectionHeader label={$t`Tags`} level="l1" />
          {/if}
          <TagsList folder={selectedFolder} bind:searchMessages showStaticLabel={false} />
        </vbox>
      {/if}
      <hbox class="footer">
        <ViewSwitcher />
      </hbox>
    {/if}
  </vbox>
</LeftPane>

<script lang="ts">
  import type { MailAccount } from "../../../logic/Mail/MailAccount";
  import { type Folder } from "../../../logic/Mail/Folder";
  import type { EMail } from "../../../logic/Mail/EMail";
  import type { Person } from "../../../logic/Abstract/Person";
  import { selectedPerson } from "../../../frontend/Contacts/Person/Selected";
  import { PersonUID } from "../../../logic/Abstract/PersonUID";
  import { availableTags } from "../../../logic/Abstract/Tag";
  import { SavedSearchFolder } from "../../../logic/Mail/Virtual/SavedSearchFolder";
  import { appGlobal } from "../../../logic/app";
  import LeftPane from "../../../frontend/Mail/LeftPane/LeftPane.svelte";
  import AccountList from "./AccountList.svelte";
  import FolderList from "./FolderList.svelte";
  import WriteButton from "./WriteButton.svelte";
  import TagsList from "../../../frontend/Mail/LeftPane/TagsList.svelte";
  import SearchPane from "../../../frontend/Mail/Search/SearchPane.svelte";
  import PersonsList from "../../../frontend/Contacts/Person/PersonsList.svelte";
  import GetMailButton from "../../../frontend/Mail/LeftPane/GetMailButton.svelte";
  import ViewSwitcher from "../../../frontend/Mail/LeftPane/ViewSwitcher.svelte";
  import SearchSwitcher, { SearchView } from "../../../frontend/Mail/LeftPane/SearchSwitcher.svelte";
  import Button from "../../../frontend/Shared/Button.svelte";
  import PaneHeader from "../../Shared/PaneHeader.svelte";
  import SectionHeader from "../../Shared/SectionHeader.svelte";
  import MoreIcon from "lucide-svelte/icons/ellipsis";
  import { ArrayColl, type Collection } from "svelte-collections";
  import { t } from "../../../l10n/l10n";

  export let accounts: Collection<MailAccount>; /** in */
  export let folders: Collection<Folder>; /** in */
  export let searchMessages: ArrayColl<EMail> | null; /** out */
  export let selectedAccount: MailAccount; /** in/out */
  export let selectedFolder: Folder; /** in/out */
  export let selectedFolders: ArrayColl<Folder>;
  export let activeTab: SearchView;

  let addressbooks = appGlobal.addressbooks;
</script>

<style>
  .folder-pane {
    min-width: 0;
    background-color: var(--l1-bg);
    color: var(--l1-fg);
    box-shadow: inset -1px 0 0 var(--border);
    container-type: inline-size;
  }
  :global([dir="rtl"]) .folder-pane {
    box-shadow: inset 1px 0 0 var(--border);
  }
  .mode-switcher {
    flex: none;
    padding: 0 12px 8px;
  }
  .mode-switcher :global(.island) {
    flex: 1 1 0;
  }
  .mode-switcher :global(.island > .button) {
    flex: 1 1 0;
  }
  .persons {
    min-height: 0;
  }
  .tags {
    flex: none;
    padding-block: 4px;
  }
  .tags :global(.list) {
    margin: 4px 12px 0;
  }
  .footer {
    flex: none;
    padding: 8px 12px;
    border-block-start: 1px solid var(--border);
  }
  .footer :global(.switcher) {
    margin: 0;
  }
  @container (max-width: 120px) {
    .folder-pane :global(.pane-header) {
      padding-inline: 0;
    }
    .folder-pane :global(.pane-header .middle) {
      justify-content: center;
    }
    .folder-pane :global(.pane-header .actions),
    .folder-pane :global(.pane-header .button .label),
    .folder-pane :global(.pane-header .button .gap),
    .mode-switcher,
    .tags,
    .footer {
      display: none;
    }
  }
</style>
