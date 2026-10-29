<RoundButton
  classes="sync-button"
  label={$t`Sync all calendars`}
  icon={SyncIcon}
  onClick={sync}
  loadDelayMS={0}
  {iconSize}
  padding="6px"
  border={false}
  />

<script lang="ts">
  import { appGlobal } from "../../logic/app";
  import RoundButton from "../Shared/RoundButton.svelte";
  import SyncIcon from "lucide-svelte/icons/refresh-cw";
  import { t } from "../../l10n/l10n";

  export let iconSize = "14px";

  async function sync() {
    await Promise.all(appGlobal.calendars.contents.map(cal =>
      cal.listEvents()));
  }
</script>
