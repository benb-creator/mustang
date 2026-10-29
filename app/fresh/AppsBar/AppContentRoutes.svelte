<AppContentRoutes>
  <MailRoutes slot="mail" />
  <ChatRoutes slot="chat" />
  <ContactsRoutes slot="contacts" />
  <CalendarRoutes slot="calendar" />
  <FilesRoutes slot="files" />
</AppContentRoutes>

<script lang="ts">
  import AppContentRoutes from "../../frontend/AppsBar/AppContentRoutes.svelte";
  import MailRoutes from "../Mail/MailRoutes.svelte";
  import ChatRoutes from "../Chat/ChatRoutes.svelte";
  import ContactsRoutes from "../Contacts/ContactsRoutes.svelte";
  import CalendarRoutes from "../Calendar/CalendarRoutes.svelte";
  import FilesRoutes from "../Files/FilesRoutes.svelte";
</script>
