<Thumbnail {file} preview={false} {size} />

<script lang="ts">
  import type { File } from "../../logic/Files/File";
  import Thumbnail from "./Thumbnail/Thumbnail.svelte";

  export let file: File;
  /** Size of the file type icon, when there is no preview */
  export let size = 16;
</script>
