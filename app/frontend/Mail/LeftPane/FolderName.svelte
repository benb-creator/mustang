{#if !folder.specialFolder || folder.specialFolder == SpecialFolder.Normal || folder.specialFolder == SpecialFolder.Search}
  {$folder.name}
{:else}
  {specialFolderNames[folder.specialFolder]}
{/if}

<script lang="ts">
  import { type Folder, SpecialFolder, specialFolderNames } from '../../../logic/Mail/Folder';

  export let folder: Folder;
</script>
