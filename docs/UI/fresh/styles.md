# How Fresh is styled

Fresh (`app/fresh/`) is the third frontend, next to the classic frontend (`app/frontend/`, Parula) and Lookout (`app/lookout/`). It uses the same logic, the same stores and mostly the same frontend/ components, and gives them its own look. Paths are relative to `app/`.

## Switching

- The setting `appearance.frontend` has the value `"fresh"`. Settings > General > Appearance (classic) and File > Options > General (Lookout) offer it as "Fresh".
- `frontend/MainWindow/MainWindow.svelte` loads `fresh/MainWindow/MainWindow.svelte` lazily, exactly like Lookout's root. The classic root keeps doing the startup, theme, user colours and background jobs for every frontend, and passes the Meet `sidebar` and the text direction (`rtl`) to the Fresh root.
- `fresh/MainWindow/MainWindow.svelte` imports `../app.css?inline`, appends it as a `<style>` to `<head>` and removes it in `onDestroy`, so the Fresh CSS is only in the page while Fresh is shown.
- The root element has the classes `main-window desktop fresh`. `main-window` and `desktop` are needed by global rules in `frontend/app.css` (FastList rows) and by some frontend components.

## Tokens: `fresh/app.css`

- All colours, sizes, radii, shadows, motion and type sizes are CSS variables on `:root`. Components use only these, no hard-coded colours. The full list with light and dark values is at the top of `fresh/app.css`: levels (`--spine-bg`, `--l1-bg`, `--l2-bg`, `--l3-bg`, `--float-bg`), text (`--fg-1`, `--fg-2`, `--fg-3`), `--accent*` (petrol, for actions and selection), `--signal*` (golden, for "new" and "now"), semantic colours, `--border*`, `--radius-s/-m/-l`, `--space-*`, `--font` and `--font-mono`, `--text-*` with `--line-*`, `--motion-*`, sizes like `--control-height` and `--pane-header-height`.
- They are on `:root`, never on `.fresh`: `applyColors()` (`frontend/Settings/Global/AppThemeColors.ts`) writes the user's colours from Settings > Appearance > Colors inline on `<html>`. Fresh's levels are derived from the same variables (`--l1-bg: var(--leftbar-bg)`, `--l3-bg: var(--main-bg)`, `--spine-bg: var(--appbar-bg)`, `--sel-bg: var(--selected-bg)`), so the user's colours still apply.
- Dark mode: the values in `@media (prefers-color-scheme: dark)`. The app's theme setting switches that media query (Electron's native theme), so there's no other dark-mode switch.
- The last `:root` block maps the classic variables (`--bg`, `--hover-bg`, `--selected-bg`, `--inverted-bg`, `--input-*`, `--link-*`, `--border-radius`, ...) and the existing classic component variables (`--button-radius`, `--island-radius`, `--search-field-*`, `--group-box-*`, `--pane-*`) to Fresh tokens. That's what gives frontend components that Fresh shows unchanged (Meet, Topic, Web apps, many settings pages) the Fresh colours. Don't add new per-component variables there.
- The element rules at the end apply only under `.fresh`: text inputs, `select`, `textarea` and colour fields as boxes (with `:where(.fresh)`, so a component's own scoped rule still wins), native radio and checkbox colour, text selection, the focus ring, scrollbars, and the selection states of FastList rows (accent while the list has focus, grey otherwise).
- The selected-row rules re-declare `--fg-1`, `--fg-2`, `--fg-3` and `--accent-fg` on the row's content, so its children need no special cases. A popup or context menu that the row renders next to its content keeps the floating surface and the list's colours (rule in `frontend/Shared/Popup.svelte`).

## Message content

- Mail bodies, event descriptions and chat messages are shown in their own documents (iframes). They don't see the CSS variables of the window.
- `fresh/Mail/Message/content.css` has the Fresh colours for them as plain values (light and dark). `fresh/MainWindow/MainWindow.svelte` puts it into the store `frontend/Mail/Message/contentStyle.ts` while Fresh is shown, and empties it in `onDestroy`.
- `frontend/Mail/Message/HTMLDisplay.svelte`, `frontend/Calendar/DisplayEvent/DisplayEvent.svelte`, `frontend/Calendar/Invitation/InvitationInCalendar.svelte` and `frontend/Chat/MessageView/Message.svelte` append the store's CSS to the document's `<style>`. In classic and Lookout the store is empty. The sanitizing of the content is unchanged.
- When you change a colour token, change it in `content.css` too.

## Restyling a frontend/ component for Fresh

- Reuse the frontend/ component. If it must look different in Fresh, put a `:global(.fresh) .local-class { ... }` rule into that frontend/ component, next to its own rules. Every rule must contain a local class of that component (`:global(.fresh) .button`, never `:global(.fresh) button`). Classic and Lookout don't have the `.fresh` class, so they don't change.
- Svelte scopes the first class of a selector with `.svelte-xyz` and the following ones with `:where(.svelte-xyz)`. So `:global(.fresh) .x` beats the component's own `.x`, and a rule later in the same file wins a tie.
- Fresh has its own component only where the structure differs from classic (frame, app bar, banner, pane layouts, list rows, pane headers). It has the same file name and props as the frontend/ file it corresponds to.
- Where the Fresh structure differs only in a few places, reuse the frontend/ component and add a small hook to it (next section). Copy logic only when no reuse is possible, between `<copied from="...">` / `<copied to="...">` markers in both files. Two such blocks are left: the CSS loading in `fresh/MainWindow/MainWindow.svelte` (from Lookout) and two lines of selection and view setting in `fresh/Calendar/CalendarApp.svelte`.
- Layout breakpoints are container queries, never `@media (max-width)`. The app area is the container `app` (`fresh/MainWindow/MainWindow.svelte`), the top bar is `topbar`.

## Small hooks in frontend/

A hook lets Fresh reuse a frontend/ component where its structure differs. Classic and Lookout look and behave exactly as before. The kinds of hooks, with examples:

- **A class on an element** that had none, so that a Fresh rule has a local class to select: `class="spacer"` on flex spacers, `class="page-title"` on settings page titles, `class:busy`, `class:dragging`, `class:selected`.
- **A wrapper** that is `display: contents` in classic and gets a layout in Fresh, e.g. in `frontend/Mail/Composer/MailComposer.svelte`.
- **A named slot whose fallback is the classic markup.** Fresh fills the slot with its own markup. Slot props hand the component's values and functions to Fresh, so the logic stays in the frontend component: `frontend/Mail/LeftPane/FolderLine.svelte` (`let:folderName`, `let:contextMenu`), `frontend/Mail/3pane/TableMessageListItem.svelte` (`let:toggleRead`, `let:deleteMessage`, ...), `frontend/Files/FolderLeftPane/AccountListItem.svelte` (`let:login`), `frontend/Mail/Composer/MailComposer.svelte` (slot `send` with `let:onSend`), `frontend/Settings/Window/SettingsApp.svelte` (slots `categories` and `page`).
- **A component prop whose default is the classic component.** Fresh passes its own component: `frontend/Mail/MailRoutes.svelte` (`mailApp`, `mailComposer`), `frontend/Mail/MailApp.svelte` (`verticalLayout`, `threePane`, `folderPropertiesPage`, `mailChat`), `frontend/Calendar/MainView.svelte` and `DualView.svelte` (`listView`, `weekView`, `monthView`).
- **A small prop with the classic value as default**: `initialRightRatio` (`frontend/Topic/TopicApp.svelte`, `frontend/Contacts/ContactsAppD.svelte`), `leftMinWidth` and `rightMinWidth` (ContactsAppD, SettingsApp), `menuPlacement` (`frontend/Chat/Header.svelte`). Or a component variable that became an in/out prop, so that the Fresh part in a slot can share it: `selectedAddressbook` (ContactsAppD), `listFiles` and `listDirs` (`frontend/Files/FilesAppD.svelte`), `isEncryptionExpanded` (`frontend/Mail/Message/MessageHeader.svelte`).
- **A part moved into its own file or function**, so that both UIs use it: `frontend/Calendar/SyncButton.svelte`, `frontend/Contacts/NewContactButton.svelte`, `mailMustangApp.forward()` in `frontend/Mail/MailMustangApp.ts` (was in `MessageMenu.svelte`), `isOnPathTo()` in `frontend/Shared/FastTree.ts`.
- **The store** `frontend/Mail/Message/contentStyle.ts` (see "Message content").

## The window frame

| Part | Component | Notes |
|---|---|---|
| Frame | `fresh/MainWindow/MainWindow.svelte` | workspace band, spine, app area (top bar, banner, routes, Meet sidebar) |
| Spine (app bar) | `fresh/AppsBar/AppBar.svelte` | Parula ring, apps from `mustangApps` with Lucide icons, sub-apps, "Soon" demo toggle, Settings at the bottom. The buttons are frontend's `AppButton`, `SubAppsList`, `SubAppButton`, `DemoToggle` with `:global(.fresh)` rules. The selected app is an open tab in the L1 colour. |
| Top bar | frontend `MainWindow/WindowHeader.svelte` | restyled and reordered with `:global(.fresh)` rules: title, search, workspace chip, window buttons. On macOS the traffic lights sit over the spine's top cell. |
| Workspace chip and chooser | frontend `MainWindow/WorkspaceHeader.svelte`, `WorkspaceDropDown.svelte` | `:global(.fresh)` rules |
| Banner | frontend `MainWindow/NotificationBar.svelte` | severity tint and strip as `:global(.fresh)` rules; `fresh/MainWindow/NotificationBar.svelte` puts the severity icon into its `icon` slot |
| Routes | frontend `AppsBar/AppContentRoutes.svelte` | one route table for both UIs: `fresh/AppsBar/AppContentRoutes.svelte` fills its app slots with `fresh/<App>/<App>Routes.svelte` (Mail, Calendar, Contacts, Chat, Files, Settings), and the `topic` slot with frontend's `TopicApp` with a narrower navigation column; Meet, Topic, Web apps, login and app menu are frontend pages on an L3 surface (`.page`); Setup is on the L1 canvas (`.setup-canvas`), with the Parula ring in the `setup-background` slot |

## What Fresh reuses

| App | Fresh components (`fresh/`) | Reused from frontend/ |
|---|---|---|
| Mail | `MailApp` (passes the Fresh layouts), `LeftPane/*` (account accordion, folder header, Write), `3pane/*` and `Vertical/*` (layouts and list rows), `Message/MessageDisplay`, `MessageHeader`, `MessageToolbar`, `StartPage`, `MailChat/MailChat`, `FolderPropertiesPage`, `Composer/MailComposer` (only the Send button) | `MailRoutes`, `MailApp`, `LeftPane`, `FolderList`, `FolderLine`, `AccountListItem`, `TableMessageList(Item)`, `VerticalMessageList(Item)`, `MessageBody` (sanitizing display), `MessageHeader`, `MessageToolbar`, `MessageMenu`, attachments, encryption, `Search/SearchPane`, the whole composer, `MailChat`, `FolderPropertiesPage`, `PersonsList` |
| Calendar | `CalendarApp`, `CalendarList`, `TitleBarLeft`, `TitleBarRight`, `ViewSelector`, `NewEventButton`, `DayView/WeekView`, `DayView/DayHeader`, `MonthView/MonthView`, `ListView/ListViewWithSearch` (pane headers around the classic views) | `CalendarRoutes` (event page, event editor, invitations), `MainView`, `DualView`, `DayViewGrid`, `MonthView`, `ListViewWithSearch`, `ViewSelector`, `NewEventMenu`, `SyncButton`, `ShowCalendarsButton`, `DateRange` |
| Contacts | `ContactsAppD`, `AddressbookSelector`, `PersonsToolbar`, `NewContactButton`, `PersonPage/PersonDetails` | `ContactsAppD`, `PersonsList`, `PersonsToolbar`, `PersonsActionToolbar`, `NewContactButton`, `NameBox`, `ContactBoxes`, `ContactHistory` |
| Chat | `ChatRoutes`, `Header` (New chat) | `ChatAppD` (rooms, messages, editor), `Header` |
| Files | `FilesAppD`, `LeftPane/LeftPane`, `FolderLeftPane/*` (places column on the account accordion) | `FilesRoutes`, `FilesAppD`, `LeftPane`, `FolderPane`, `AccountList(Item)`, `FolderList`, `FolderMenu`, `TagsList`, file list, gallery, details pane |
| Settings | `Window/SettingsApp`, `CategoriesPane`, `CategoryItem`, `AccountsList`, `AccountItem`, `MainContent` | `SettingsRoutes`, `SettingsApp`, the category registry and all settings pages |
| Meet, Topic, Web apps, Setup | none | all, with `:global(.fresh)` rules |

Shared controls: Fresh uses frontend/Shared's controls (`Button`, `RoundButton`, `Checkbox`, `IslandSwitcher` as segmented control, `SearchField`, `Menu`, `ContextMenu`, `ButtonMenu`, `Popup`, `Splitter`, tags, `ProgressBar`, `Spinner`, `ErrorMessageInline`, ...), restyled with `:global(.fresh)` rules. `fresh/Shared/` has only those that frontend/ has no component for: `PaneHeader`, `SectionHeader`, `NavRow`, `AccountRow`, `AccountAccordion`, `Badge`, `EmptyState`, `SplitButton`, `TabBar` and `Tab`.

## Adding a screen

1. Start from the `fresh/<App>/<App>Routes.svelte` of that app. It renders frontend's routes or app component and fills their slots or component props with Fresh components. An app without its own Fresh routes shows the frontend app.
2. Replace a frontend component by a Fresh one only where the structure differs, with the same name, path and props as the frontend/ file. Compose frontend/ engines (FastList, Splitter, stores, `open.ts` helpers, message display) and the shared controls (frontend/Shared, restyled for Fresh, plus `fresh/Shared/` for the few that frontend/ doesn't have).
3. Take colours and sizes from the tokens. Check light and dark mode, and a narrow window.
4. Buttons that only show on hover (row actions) must also show while something in the row has keyboard focus, and stay focusable while hidden (`opacity: 0`, not `display: none`), as in `fresh/Shared/NavRow.svelte`.
5. Functionality the screen would want, but logic/ or frontend/ doesn't offer, goes into `docs/UI/fresh/missing-functionality.md`, not into code.
