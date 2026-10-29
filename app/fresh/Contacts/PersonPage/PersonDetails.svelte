<vbox flex class="person-page" bind:clientWidth={pageWidth}>
  <PaneHeader level="l3" tall>
    <NameBox {person} bind:isEditing />
  </PaneHeader>

  {#if pageWidth && pageWidth < kSideBySideWidth}
    <TabBar bind:selected={section}>
      <Tab id="details" label={$t`Details`} />
      <Tab id="history" label={$t`Contact history *=> The log of previous interactions with this person`} />
    </TabBar>
    {#if section == "history"}
      <vbox flex class="history">
        <ContactHistory {person} />
      </vbox>
    {:else}
      <vbox flex class="boxes">
        <Scroll hideHorizontalScrollbar={true}>
          <ContactBoxes {person} bind:isEditing showExpanders={true} />
        </Scroll>
      </vbox>
    {/if}
  {:else}
    <Splitter initialRightRatio={1} name="contact-history" rightMinWidth={240}>
      <vbox flex class="boxes" slot="left">
        <Scroll hideHorizontalScrollbar={true}>
          <ContactBoxes {person} bind:isEditing showExpanders={true} />
        </Scroll>
      </vbox>
      <vbox flex class="history side" slot="right">
        <ContactHistory {person} />
      </vbox>
    </Splitter>
  {/if}
</vbox>

<script lang="ts">
  import type { Person } from "../../../logic/Abstract/Person";
  import NameBox from "../../../frontend/Contacts/PersonPage/NameBox.svelte";
  import ContactBoxes from "../../../frontend/Contacts/PersonPage/ContactBoxes.svelte";
  import ContactHistory from "../../../frontend/Contacts/History/ContactHistory.svelte";
  import PaneHeader from "../../Shared/PaneHeader.svelte";
  import TabBar from "../../Shared/TabBar.svelte";
  import Tab from "../../Shared/Tab.svelte";
  import Splitter from "../../../frontend/Shared/Splitter.svelte";
  import Scroll from "../../../frontend/Shared/Scroll.svelte";
  import { t } from "../../../l10n/l10n";

  export let person: Person;

  let isEditing = false;

  const kSideBySideWidth = 800;
  let pageWidth = 0;
  let section = "details";
</script>

<style>
  .person-page {
    min-width: 0;
    min-height: 0;
    container-type: inline-size;
  }
  .person-page > :global(.tab-bar) {
    padding-inline: 16px;
  }
  .boxes {
    min-width: 0;
    min-height: 0;
    padding-block-start: 8px;
  }
  .history {
    min-width: 0;
    min-height: 0;
    padding-block-start: 8px;
  }
  .history.side {
    border-inline-start: 1px solid var(--border-subtle);
  }
</style>
