<hbox flex class="person">
  <PersonPicture person={person?.person} size={32} />
  <vbox flex class="right">
    <hbox class="top-row">
      <hbox flex class="name font-normal">{person.name}</hbox>
    </hbox>
    <hbox class="bottom-row">
      <hbox class="email-address font-small">
        {person.emailAddress}
      </hbox>
      <slot name="bottom-row" />
    </hbox>
  </vbox>
</hbox>

<script lang="ts">
  import type { PersonUID } from "../../../logic/Abstract/PersonUID";
  import PersonPicture from "../Person/PersonPicture.svelte";

  export let person: PersonUID;
</script>

<style>
  .person,
  .name {
    align-items: center;
  }
  .name {
  }
  .email-address {
    opacity: 50%;
    overflow: hidden;
    align-items: center;
  }
  .person :global(.avatar) {
    margin: 0px;
    margin-inline-end: 6px;
  }
  .top-row,
  .bottom-row {
    height: 16px;
    overflow: hidden;
    white-space: nowrap;
    align-items: center;
  }

  :global(.fresh) .person {
    --person-picture-size: 32px;
    gap: 8px;
    min-width: 0;
  }
  :global(.fresh) .person :global(.avatar) {
    margin: 0;
  }
  :global(.fresh) .top-row,
  :global(.fresh) .bottom-row {
    height: auto;
  }
  :global(.fresh) .name {
    font-size: var(--text-m);
    line-height: var(--line-m);
    font-weight: 600;
    color: var(--fg-1);
  }
  :global(.fresh) .email-address {
    font-size: var(--text-s);
    line-height: var(--line-s);
    color: var(--fg-2);
    opacity: 1;
  }
</style>
