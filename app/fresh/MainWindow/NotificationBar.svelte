<NotificationBar {notifications}>
  <hbox class="severity-icon" slot="icon" let:severity {severity}>
    <svelte:component this={severityIcons[severity] ?? InfoIcon} size="16px" />
  </hbox>
</NotificationBar>

<script lang="ts">
  import { NotificationSeverity, type Notification } from "../../logic/util/Notification";
  import NotificationBar from "../../frontend/MainWindow/NotificationBar.svelte";
  import ErrorIcon from "lucide-svelte/icons/circle-alert";
  import WarningIcon from "lucide-svelte/icons/triangle-alert";
  import LoggedOutIcon from "lucide-svelte/icons/plug-zap";
  import InfoIcon from "lucide-svelte/icons/info";
  import type { ArrayColl } from "svelte-collections";

  export let notifications: ArrayColl<Notification>;

  const severityIcons = {
    [NotificationSeverity.UnexpectedError]: ErrorIcon,
    [NotificationSeverity.Error]: ErrorIcon,
    [NotificationSeverity.Warning]: WarningIcon,
    [NotificationSeverity.LoggedOut]: LoggedOutIcon,
    [NotificationSeverity.Info]: InfoIcon,
  };
</script>

<style>
  .severity-icon {
    flex: 0 0 auto;
    color: var(--info-fg);
  }
  .severity-icon[severity="meltdown"],
  .severity-icon[severity="error"] {
    color: var(--danger-fg);
  }
  .severity-icon[severity="warning"],
  .severity-icon[severity="logged-out"] {
    color: var(--warning-fg);
  }
  :global(.custom-colors) > .severity-icon {
    color: inherit;
  }
</style>
