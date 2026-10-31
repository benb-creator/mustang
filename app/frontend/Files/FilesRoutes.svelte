{#if appGlobal.isMobile}
  <Route path="person/:personID/upload">
    <UploadM person={params?.person ?? $selectedPerson ?? requiredParam()} />
  </Route>
  <Route path="person/:personID/files">
    <FilesM person={params?.person ?? $selectedPerson ?? requiredParam()} />
  </Route>
  <Route path="search">
    <PersonsM selectedPerson={params?.person ?? $selectedPerson} doSearch={true} />
  </Route>
  <Route path="file">
    <vbox flex class="file-page">
      <FileViewer file={params?.file ?? requiredParam()} size={96} />
    </vbox>
    <FilesBarM />
  </Route>
  <Route path="/">
    <PersonsM selectedPerson={params?.person ?? $selectedPerson} />
  </Route>
{:else}
  <Route path="file">
    {$viewFile = params?.file ?? requiredParam()}
    <FilesAppD />
  </Route>
  <Route path="/">
    <FilesAppD />
  </Route>
{/if}

<script lang="ts">
  import { selectedPerson } from "../Contacts/Person/Selected";
  import { viewFile } from "./selected";
  import { appGlobal } from "../../logic/app";
  import FilesAppD from "./FilesAppD.svelte";
  import FileViewer from "./FileViewer.svelte";
  import PersonsM from "./PersonsM.svelte";
  import FilesM from "./FilesM.svelte";
  import UploadM from "./UploadM.svelte";
  import FilesBarM from "./FilesBarM.svelte";
  import { getParams } from "../AppsBar/selectedApp";
  import { requiredParam } from "../Util/route";
  import { Route, useLocation } from "svelte-navigator";

  $: location = useLocation();
  $: params = getParams($location?.state);
</script>

<style>
  .file-page {
    align-items: center;
    justify-content: center;
    background-color: var(--main-bg);
    color: var(--main-fg);
  }
</style>
