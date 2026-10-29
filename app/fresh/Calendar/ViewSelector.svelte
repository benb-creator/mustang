<ViewSelector bind:dateInterval let:dateIntervalLabel>
  <hbox class="view-selector">
    <hbox class="segments">
      <IslandSwitcher>
        {#each kMainIntervals as interval}
          <Button
            label={dateIntervalLabel(interval)}
            selected={dateInterval == interval}
            onClick={() => dateInterval = interval}
            />
        {/each}
        <Button
          label={isMoreSelected ? dateIntervalLabel(dateInterval) : $t`More views`}
          icon={ChevronDownIcon}
          iconOnly={!isMoreSelected}
          selected={isMoreSelected}
          classes="more"
          onClick={() => isMenuOpen = !isMenuOpen}
          bind:buttonEl={moreButtonE}
          />
      </IslandSwitcher>
    </hbox>
    <select class="select" bind:value={dateInterval} title={$t`View *=> Which calendar view to show: day, week, month or list`}>
      {#each kMainIntervals.concat(kMoreIntervals) as interval}
        <option value={interval}>{dateIntervalLabel(interval)}</option>
      {/each}
    </select>
  </hbox>
  <Menu bind:isMenuOpen anchor={moreButtonE} placement="bottom-end">
    {#each kMoreIntervals as interval}
      <MenuItem
        label={dateIntervalLabel(interval)}
        selected={dateInterval == interval}
        onClick={() => dateInterval = interval}
        />
    {/each}
  </Menu>
</ViewSelector>

<script lang="ts">
  import type { DateInterval } from "../../frontend/Calendar/selected";
  import ViewSelector from "../../frontend/Calendar/ViewSelector.svelte";
  import IslandSwitcher from "../../frontend/Shared/IslandSwitcher.svelte";
  import Button from "../../frontend/Shared/Button.svelte";
  import Menu from "../../frontend/Shared/Menu/Menu.svelte";
  import MenuItem from "../../frontend/Shared/Menu/MenuItem.svelte";
  import ChevronDownIcon from "lucide-svelte/icons/chevron-down";
  import { t } from "../../l10n/l10n";

  export let dateInterval: DateInterval; /* in/out */

  const kMainIntervals: DateInterval[] = [1, 5, 7, 31, 0];
  const kMoreIntervals: DateInterval[] = [2, 28];

  let isMenuOpen = false;
  let moreButtonE: HTMLButtonElement;
  $: isMoreSelected = kMoreIntervals.includes(dateInterval);
</script>

<style>
  .view-selector {
    flex: none;
    align-items: center;
  }
  .view-selector :global(.button.more) {
    gap: 4px;
  }
  .select {
    display: none;
    width: auto;
  }
  @container calendar-pane (max-width: 760px) {
    .segments {
      display: none;
    }
    .select {
      display: block;
    }
  }
</style>
