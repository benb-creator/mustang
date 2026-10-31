<AppMenuRow app={webAppsMustangApp} page="/webapps/">
  <AccountButton account={appGlobal.webApps.apps.contents[3]} page={app => `/webapps/app/${app.id}/start`} />
  <AccountButton account={appGlobal.webApps.apps.contents[2]} page={app => `/webapps/app/${app.id}/start`} />
  <AccountButton account={appGlobal.webApps.apps.contents[1]} page={app => `/webapps/app/${app.id}/start`} />
  <AccountButton account={appGlobal.webApps.apps.contents[0]} page={app => `/webapps/app/${app.id}/start`} />
</AppMenuRow>

<script lang="ts">
  import { webAppsMustangApp } from "../../../WebApps/WebAppsMustangApp";
  import { appGlobal } from "../../../../logic/app";
  import AccountButton from "../AccountButton.svelte";
  import AppMenuRow from "../AppMenuRow.svelte";
</script>
