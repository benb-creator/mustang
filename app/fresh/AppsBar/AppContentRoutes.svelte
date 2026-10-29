<AppContentRoutes>
  <MailRoutes slot="mail" />
  <ContactsRoutes slot="contacts" />
  <CalendarRoutes slot="calendar" />
</AppContentRoutes>

<script lang="ts">
  import AppContentRoutes from "../../frontend/AppsBar/AppContentRoutes.svelte";
  import MailRoutes from "../Mail/MailRoutes.svelte";
  import ContactsRoutes from "../Contacts/ContactsRoutes.svelte";
  import CalendarRoutes from "../Calendar/CalendarRoutes.svelte";
</script>
