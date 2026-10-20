# How Lookout restyles the frontend/ components it shows

Lookout (`app/lookout/`) is the Outlook-like frontend. It shows some components of the classic frontend (`app/frontend/`, also called Parula) as they are. This document explains how they get Lookout's look. Paths are relative to `app/`.

## Summary

- Lookout has one global stylesheet, `lookout/app.css`. Lookout's MainWindow adds it as a `<style>` element when Lookout starts, and removes it when the user switches back to Parula.
- The main trick is the second `:root` block in `lookout/app.css`: the classic variables (`--bg`, `--selected-bg`, `--hover-bg`, `--leftbar-bg`, `--appbar-bg`, `--border-radius`, ...) are set to Lookout's `--lo-*` palette. Every frontend/ component that uses those variables gets Lookout's colors, in light and dark mode, with no change to the component. That is most of what Web apps, Files, Chat, Meet and Topic get.
- The same file sets the font, and adds a few global rules (scrollbars, text selection, focus ring, checkboxes, popup menus) and the generic list classes `nav-list` and `nav-entry`.
- Where a frontend component needs a different shape or spacing in Lookout, the component itself has `:global(.lookout) .foo` rules, like the `:global(.mobile) .foo` rules for mobile (see 1.5). Lookout doesn't add CSS variables for single components to `app.css`, because that doesn't scale. The Web apps store categories also use `nav-list` and `nav-entry` (see 1.6). Setup, the frontend settings pages and the notification bar also get `:global(...)` overrides from Lookout components.
- What can't be changed globally: px sizes, hard-coded colors (e.g. Parula teal `#20AE9E`) and px font sizes in frontend/ scoped CSS, plus the iframes that show mail and event bodies.
- Mail, Calendar, People, the Settings window, app bar, ribbon, dialogs and menus are Lookout's own components, which use `--lo-*` directly.

## 1. The mechanisms

### 1.1 How `lookout/app.css` is loaded and removed

- `frontend/main.ts` always imports `frontend/app.css` (Parula's variables, Karla font, base rules). It stays loaded in Lookout too.
- `frontend/MainWindow/MainWindow.svelte` reads the `appearance.frontend` setting. If it's "lookout", it loads `lookout/MainWindow/MainWindow.svelte` lazily with `import()`.
- `lookout/MainWindow/MainWindow.svelte` imports `../app.css?inline`, so Vite returns the CSS as a string and doesn't apply it. The component puts the string into a `<style>` at the end of `<head>` and removes it in `onDestroy`. A comment there says why: if the user switches to the classic frontend at runtime, the global CSS has to go away.
- That `<style>` comes after `frontend/app.css`, so its `:root` rules win at equal specificity. The mapping block isn't inside the dark `@media` block. It points to `--lo-*` variables, which have their own dark values (the `@media (prefers-color-scheme: dark)` block in `lookout/app.css`), so dark mode works for every mapped variable.
- Lookout's root element has the classes `main-window desktop lookout` (`lookout/MainWindow/MainWindow.svelte`). `main-window` is needed: the global FastList hover rules in `frontend/app.css` start with `.main-window:not(.mobile)`, and they apply in Lookout because of it.

### 1.2 Variable mapping: colors

The Lookout palette is the first `:root` block of `lookout/app.css` (light) and the `@media (prefers-color-scheme: dark)` block after it. The mapping is the second `:root` block. These are the mapped variables with the most visible effect:

| Classic variable | In Lookout | In Parula | Effect in frontend apps |
|---|---|---|---|
| `--bg`, `--main-bg` | `--lo-pane-bg` (white, dark #26272B) | white | |
| `--selected-bg` | `--lo-selected-bg` (#D4E4F7 pale blue, dark #253A55) | #20AE9E teal | selection is pale blue |
| `--selected-fg` | `--lo-fg` (normal text color) | white | selected text keeps the normal text color |
| `--hover-bg` | `--lo-hover-bg` (#EEF1F5) | #A9DAD4 | |
| `--leftbar-bg` | `--lo-pane-bg` (white) | #F9F9FD | left panes have the same color as the center |
| `--appbar-bg` | `--lo-window-bg` (#EDF1F6 grey) | #494558 dark purple | e.g. the Web apps launch bar |
| `--headerbar-bg` | `--lo-window-bg` | #EEEEEE | |
| `--inverted-bg` | `--lo-accent` (blue) | #160C27 | "filled" buttons are blue |
| `--icon-primary`, `--input-focus` | `--lo-accent` | teal | |
| `--offset-bg` | `--lo-accent-tint` | #E6F2F1 | |
| `--border`, `--button-*`, `--input-*`, `--link-*` | Lookout equivalents | | |
| `--border-radius` | `--lo-radius-small` (4px) | 5px | the only shape variable, used by 7 frontend rules |

Not mapped, so they keep Parula's values in Lookout: `--chat-bubble-*` (outgoing chat bubbles stay mint #CDECE1), `--shadow-color` and `--thread-*` (all in `frontend/app.css`).

Caveat: the custom colors from Parula's Appearance settings (Background, Center, Left bar, App bar, Selection) are set as an inline style on `<html>` by `applyColors()` in `frontend/Settings/Global/AppThemeColors.ts`. `frontend/MainWindow/MainWindow.svelte` calls it in Lookout too, and an inline style beats `:root`. So a user's custom `--selected-bg` from Parula shows in Web apps and Files in Lookout, but not in Lookout's own components.

### 1.3 Font

- `lookout/app.css` sets `font-family: var(--lo-font)` (Segoe UI Variable, Segoe UI, system-ui) on `:root`, which replaces Karla (the `font-family` on `:root` in `frontend/app.css`). Its `body` rule sets 14px. The `.lookout` rule in `lookout/MainWindow/MainWindow.svelte` sets both again.
- This reaches all frontend text that doesn't set its own font.
- It doesn't reach px font sizes in frontend scoped CSS (63 declarations in 55 files, e.g. the buttons in `frontend/Shared/Button.svelte`). It also doesn't reach the global classes `.font-smallest/.font-small/.font-normal/.font-large` (`frontend/app.css`, 12/14/16/24px), which Lookout doesn't override.

### 1.4 Global rules in `lookout/app.css`

- `*::selection` (text selection), `:focus-visible` (focus ring, replaces the one in `frontend/app.css`), `::-webkit-scrollbar*` (scrollbars), and `accent-color` of native checkboxes and radio buttons. All of these are colors.
- `.lookout .popup > .menu`: border, 8px radius and popup shadow for frontend popup menus (`frontend/Shared/Popup.svelte`, `frontend/Shared/Menu/Menu.svelte`). `.popup` keeps its own 5px radius and shadow (`Popup.svelte`).
- `.lookout .checkbox ...`: colors for the frontend `Shared/Checkbox.svelte`.
- `.lo-card`, `.lo-secondary`, `.lo-text-field`: helper classes. Only Lookout's own components use them.
- `.lookout .nav-list ...`: the shared style of navigation lists, see 1.6.

### 1.5 `:global(.lookout)` rules in frontend components, and wrappers and overrides in Lookout components

- frontend/ components with Lookout rules: `:global(.lookout) .foo` in the component's own `<style>`, next to the classic rule it changes. `.foo` is always a class of that component, so the rule stays scoped. Currently:
  - controls: `Shared/Button.svelte` (small radius, 32px high, accent hover of filled buttons), `Shared/RoundButton.svelte` (small radius, accent hover of filled buttons), `Shared/IslandSwitcher.svelte` (small radius, no overlap, bold selected button), `Shared/SearchField.svelte` (small radius, input background), `Shared/HeaderGroupBox.svelte` (no box, header with a line below, like Lookout's sections)
  - panes, each one its own card like in Mail and Contacts: `Chat/ChatAppD.svelte`, `Files/FilesAppD.svelte`, `Settings/Window/SettingsApp.svelte`, `WebApps/WebAppsApp.svelte`. The navigation panes sit on the window background without shadow: `Files/LeftPane/LeftPane.svelte`, `Settings/Window/CategoriesPane.svelte`, `WebApps/Shop/WebAppStore.svelte`
  - persons list like in Contacts: `Contacts/Person/PersonsList.svelte`, `Contacts/Person/PersonLine.svelte`, `Files/LeftPane/PersonsPane.svelte`
- The `:global(.lookout)` prefix makes such a rule one class more specific than the classic rule. A caller's own override of the component, e.g. the flat buttons of `Shared/Toolbar/Toolbar.svelte`, can then lose in Lookout. The Button rules therefore wrap their `:not(.plain)` in `:where()`.
- `lookout/AppsBar/AppContentRoutes.svelte` wraps the meet, topic, login and app-menu routes in `<vbox class="frontend-page">`. Its `.frontend-page` rule gives a 4px 8px 8px 8px margin, the pane background, `--lo-radius` (8px), a card shadow, and `overflow: hidden`. The chat, files, webapp and settings routes get `<vbox class="frontend-panes">` instead, which only has a margin, because their panes are cards themselves.
- `lookout/Setup/SetupRoutes.svelte` wraps frontend Setup. It hides the background video, turns `.page-box` into a card (margin, radius, border, shadow), and sets the heading weight and input font.
- `lookout/Settings/Window/MainContent.svelte` restyles frontend settings pages shown in Lookout's Settings window: `h2` size, `.group` bottom margin, group header font size, input font. It sets `--headerbar-bg: transparent`, the only place where Lookout sets a classic variable for a subtree only.
- `lookout/MainWindow/MainWindow.svelte` restyles the frontend NotificationBar with `.app-area > :global(.notification-bar ...)` rules (margin, radius, infobar colors, and it hides the leading spacer, so the message is left-aligned). Its `.sidebar` rule gives the Meet sidebar a shadow.
- Lookout's own components that embed frontend parts override them for that one place: FastList rows (`lookout/Contacts/Person/PersonsList.svelte`, `PersonsTable.svelte`, `lookout/Mail/Rules/Rules.svelte`, `lookout/Mail/Composer/SelectNamesDialog.svelte`), and HTMLEditor (`lookout/Mail/Composer/MailComposer.svelte`, which changes the blockquote border from teal to the accent color).
- Most of the ~250 `:global(...)` rules in lookout/ style Lookout's own child elements and icons, not frontend components.

### 1.6 Copies with `<copied>` markers, and the shared list style

If a frontend component's markup or CSS couldn't be changed from outside, Lookout copied it and styled the copy: 121 `<copied from="…frontend/…">` blocks in 69 Lookout files (e.g. encryption key pages, TimeBox, settings categories). frontend/ has no `<copied to=…>` markers pointing back, so a change to an original doesn't show that Lookout has a copy.

Lookout's own components never use the classic variables: `var(--lo-selected-bg)` appears about 40 times in lookout/ components, `var(--selected-bg)` never. Most lists write out their own row style (pale selection, 4px radius, 3px accent bar, bold when selected), e.g. the mail folders (`.folder-row` in `lookout/Mail/LeftPane/FolderLine.svelte`) and the calendars (`lookout/Calendar/CalendarListItem.svelte`). The accent bar is in 10 component files.

Navigation lists share one style instead, defined once in `lookout/app.css`:

- `nav-list` goes on the list. It gives the 4px inset at both sides (`padding-inline`), so all entries, also indented sub-entries, have the same width.
- `nav-entry` goes on each entry. It gives the 4px radius (`--lo-radius-small`), the hover color (`--lo-hover-bg`), the selection color (`--lo-selected-bg`, also when the selected entry is hovered), bold text and the 3px accent bar (`::before`, `--lo-accent`) of the selected entry. The entry is selected when it has the class `selected`.
- Each list keeps its own height, padding and indentation. Sub-entries are indented with padding inside the entry, not with a margin, so their highlight fills the line like a main entry.
- Users: the Settings categories (`lookout/Settings/Window/CategoriesPane.svelte`, `CategoryItem.svelte`, `AccountItem.svelte`, `AccountsList.svelte`), the address book list in People (`lookout/Contacts/AddressbookSelector.svelte`, `AddressbookItem.svelte`) and the Web apps store categories (`frontend/WebApps/Shop/WebAppStore.svelte`, `CategoryEntry.svelte`).
- The store is a frontend component. Its markup only carries the two class names. frontend/ has no CSS for them, so Parula's store looks the same as before.
- The rules start with `.lookout .nav-list`, so they win over the store's own scoped selection rules (up to specificity 0,4,0).

### 1.7 What can't be changed globally today

- Spacing and shape in frontend scoped CSS: 1306 px padding and margin declarations in 359 files. There are 107 px `border-radius` values in 88 files, but only 7 uses of `var(--border-radius)`. Buttons are pills with `border-radius: 1000px` (`frontend/Shared/Button.svelte`, `RoundButton.svelte`). Button is imported by 139 files, RoundButton by 89.
- Hard-coded colors: 390 in 161 frontend files. Some are copies of Parula's palette:
  - teal `#20AE9E`/`#20AF9E`, e.g. `frontend/Shared/Spinner.svelte`, `frontend/Shared/Editor/HTMLEditor.svelte`, and 4 places in Meet. The Spinner is used by Button and RoundButton (loading state), by Setup, and by Lookout's composer.
  - app bar purple `#494558`, e.g. the Meet sidebar (`frontend/Meet/ParticipantsBar/Sidebar.svelte`) and `frontend/Meet/Start/Calling.svelte`
  - grey text: 39 `color:` greys in 33 files
- In Parula, `--selected-bg` is also the accent color (teal). Lookout separates the two: pale selection, strong blue accent. So places that use teal as an accent can't become Lookout blue through the mapping.
- px font sizes (see 1.3).
- Iframes: the mail body and the event description are shown in a WebView with `frontend/Mail/Message/content-body.css`. It sets the Karla font, Parula's dark background #141416 and teal text selection. The iframe is a separate document, so no variable reaches it. In Lookout's dark mode, the mail body is darker than the pane around it.
- Selection is painted per grid cell in FastList and in the Files table (rows are `display: contents`). So a radius or an accent bar needs `:first-child`/`:last-child` rules, not just one property on the row.

## 2. Per app

| App | In Lookout | Where its style comes from |
|---|---|---|
| Mail | Own (`lookout/Mail/`) | `--lo-*`. Embeds frontend MessageBody (iframe, not restyled), HTMLEditor and FastList, each with its own `:global` overrides |
| Calendar | Own (`lookout/Calendar/`) | `--lo-*`. Embeds frontend WebView (event description iframe) and Splitter |
| People | Own (`lookout/Contacts/`) | `--lo-*`. FastList restyled where it's used. The address book list uses `nav-list` and `nav-entry` |
| Settings | Mixed | Lookout's Settings window and Backstage (`lookout/Settings/`). Its categories use `nav-list` and `nav-entry`. It has 14 own pages and 11 frontend pages (`lookout/Settings/SettingsCategories.ts`), restyled by `MainContent.svelte`. The `settings/*` route still shows Parula's Settings in a card. Frontend code gets there via `openSettingsCategory…`, e.g. `frontend/Setup/Files/SetupFiles.svelte`, `frontend/Files/FolderLeftPane/NoAccounts.svelte`, `frontend/WebApps/Shop/AddDialog.svelte` |
| Setup | frontend, wrapped | `lookout/Setup/SetupRoutes.svelte`. The "new folder account" dialog is Lookout's own |
| Web apps and store | frontend, in the card | Variable mapping and card. The store categories use `nav-list` and `nav-entry` |
| Files | frontend, in the card | Variable mapping and card only |
| Chat | frontend, in the card | Variable mapping and card. Chat bubbles keep Parula's colors |
| Meet | frontend, in the card | Variable mapping and card, plus the sidebar shadow. 43 hard-coded colors (teal, purple) stay |
| Topic | frontend, in the card | Variable mapping and card only |
| Login (OAuth2), app menu | frontend, in the card | Variable mapping and card only |
| App bar, title bar, status bar, ribbon, Backstage, dialogs, menus, message boxes | Own | `--lo-*` |
| Notification bar | frontend, restyled | `lookout/MainWindow/MainWindow.svelte` |
| Frontend popup menus and checkboxes (inside the frontend apps) | frontend, restyled | `lookout/app.css` |

## 3. Web apps store categories and Files

### Store category list (`frontend/WebApps/Shop/`)

This CSS reaches it in Lookout, from the outside in:

1. The store is in the `.main-pane` card of `WebAppsApp.svelte` (see 1.5).
2. The `.categories` pane in `WebAppStore.svelte`:
   - background and text from `--leftbar-bg/fg`, which in Lookout are white and Lookout's text color
   - padding 40px at the top and 24px at the bottom. In Lookout, its class `nav-list` adds 4px at the sides.
   - a hard-coded shadow `rgba(22, 12, 39, 8%)`, which its `:global(.lookout)` rule removes
   - the class `font-small` makes it 14px (`frontend/app.css`). The font family comes from `lookout/app.css`.
3. `.category` in `CategoryEntry.svelte`. Rows have 6px/24px padding, and selection and hover use `--selected-bg/-fg`, `--hover-bg/-fg` and `--selected-hover-bg/-fg`. Through the variable mapping, these are already Lookout's colors in light and dark mode: pale blue selection (dark blue in dark mode), grey hover, normal text color.
4. The class `nav-entry` on the rows (see 1.6). In Lookout, it gives the rows the 4px radius, bold text and the accent bar when selected, and keeps the selection color when the selected row is hovered, the same as in the Settings categories.

The launch bar next to the store uses `--appbar-bg` (`LauncherBar/LaunchBar.svelte`), which is Lookout's grey window color. Its hover and selected colors are hard-coded for Parula's dark bar: white at 25% and 95%, with black labels (`LauncherBar/LaunchBarButton.svelte`).

### Files (`frontend/Files/`)

1. The main pane and the right pane are cards (`FilesAppD.svelte`, see 1.5).
2. Left pane (`LeftPane/LeftPane.svelte`): `--leftbar-bg` makes it white. Its `:global(.lookout)` rule removes the hard-coded shadow `rgba(0, 0, 0, 10%)`.
3. The account list and folder tree are FastList and FastTree (`FolderLeftPane/AccountList.svelte`, `FolderLeftPane/FolderList.svelte`).
   - Selection and hover come from the global `.fast-list .row` rules in `frontend/app.css`, so they have Lookout's colors.
   - Row padding is `0 5px` (`frontend/Shared/FastList.svelte`).
   - Hard-coded: 14px and a grey header (`FolderList.svelte`), and a `#555555` expander (`frontend/Shared/FastTreeItem.svelte`).
4. File table: `FilesList/FileLine.svelte` and `FilesList/DirectoryLine.svelte` have identical CSS: `.line.selected > *` and `.line:hover > *` with the classic variables, so Lookout's colors. Paddings are px. The type, size and date columns are hard-coded `#91939D` (both files). The header borders use `--border` (`FilesList.svelte`).
5. Gallery: hover only, via `--hover-bg` (`Gallery/FileTile.svelte`, `Gallery/DirectoryTile.svelte`).
6. Right pane: hard-coded shadow color `#e3e3e3` (`RightSidePane/FileRightPane.svelte`).

### What a Lookout-only style for selected and hover rows would have to touch

The store categories have it already, with `nav-list` and `nav-entry` (see 1.6). Their frontend markup only needed the two class names. For the Files lists, there are two ways:

A. Only lookout/ files, with `:global` overrides in `lookout/AppsBar/AppContentRoutes.svelte`, or in `lookout/app.css` under `.lookout`:
   - Files table: radius on `.frontend-page :global(.files-list .line.selected > :first-child)` and on `:last-child`, with the accent bar on the first cell. The same for hover.
   - Files left pane: `.fast-list .row.selected > *`. In `lookout/app.css`, this would also change Lookout's own FastList lists (Contacts, Select Names, Rules), which already have their own rules.
   - Each override needs the wrapper prefix to beat the scoped rule, because Svelte adds a class to it (`.line.selected` becomes specificity 0,3,0).
   - Downside: it depends on frontend's internal class names (`.line`, `.row`, `.selected`), and nothing in frontend/ shows that Lookout uses them. The generic class names avoid that, as in the store.

B. In the frontend components: `:global(.lookout)` rules in `FileLine.svelte` and `DirectoryLine.svelte`, next to their classic row rules (see 1.5). Parula's look doesn't change. See recommendation 3.

## 4. Recommendations for sharing more and styling globally

Ranked by benefit. Each one keeps Parula's look by default. A variable is only worth it for a theme value that many components use, like the accent color. A look that only a few components need goes into these components as `:global(.lookout)` rules (see 1.5).

1. **Done: button radius.** `frontend/Shared/Button.svelte` and `RoundButton.svelte` have `:global(.lookout)` rules with `--lo-radius-small` instead of the pill radius. Plain buttons (3px) stay as they are.
2. **A real accent variable.** Add `--accent` and `--accent-fg` to `frontend/app.css` (Parula: teal #20AE9E and white), and set them to `--lo-accent` in Lookout. Use it where teal is hard-coded as an accent: `Shared/Spinner.svelte`, `Shared/Editor/HTMLEditor.svelte` (then Lookout's blockquote override in `MailComposer.svelte` can go), `Settings/Mail/Send.svelte`, and the Meet buttons (`Meet/InMeetingToolbar.svelte`, `Meet/Start/Calling.svelte`, `Meet/Start/Phone/PhoneDialScreen.svelte`). That's about 6 files in frontend/.
3. **List-row look** (this covers Files). The store categories already get Lookout's row look from `nav-list` and `nav-entry` (see 1.6). The two row styles that Lookout shows and that don't have these classes are FastList (`.fast-list .row` in `frontend/app.css`) and Files (`FileLine.svelte`, `DirectoryLine.svelte`). They need:
   - a 4px radius on the first and last cell
   - an accent bar (`--lo-accent`) drawn on the first cell with `::before` and `inset-inline-start`, the way Lookout's own rows do it
   - weight 600 for the selected row

   These are the same values as `nav-entry`. For Files, these are `:global(.lookout)` rules in the 2 files. An inset works easily only on flex rows, like with `nav-list`. In the grid lists, it would be padding on the container.
4. **Lookout-only additions to `lookout/app.css`**, with no frontend change:
   - Map the variables that are still missing: `--chat-bubble-*` (Chat) and `--shadow-color` (Popup, person popup, Meet popups).
   - Override `.font-smallest/.font-small/.font-normal/.font-large` with Lookout's sizes. Lookout's own components don't use these classes, and 31 files in Web apps, Files, Chat, Meet and Topic do.

   That's about 15 lines.
5. **A `--secondary-fg` variable for dim text.** It replaces 39 hard-coded greys in 33 files, e.g. `#91939D` in the Files table and `grey` in `Files/FolderLeftPane/FolderList.svelte`. Lookout sets it to `--lo-fg-secondary`. It also fixes contrast in Parula's dark mode. This can be done app by app, whenever a file is touched anyway.
6. **Shadows through `--shadow-color`.** Replace the literal `rgba(22, 12, 39, x)` (6 places, e.g. `frontend/WebApps/Shop/WebAppStore.svelte` and `frontend/Settings/Window/CategoriesPane.svelte`) and the pane shadows with `rgba(0, 0, 0, x)` (e.g. `frontend/Files/LeftPane/LeftPane.svelte`) with `rgba(var(--shadow-color), x)`. Little effort, small benefit.
7. **Optional: iframe colors.** `frontend/Mail/Message/HTMLDisplay.svelte` and `lookout/Calendar/DisplayEvent/DisplayEvent.svelte` build the iframe's `<style>`. They could add the current values of `--bg`, `--fg`, the font and the selection color to it. Then mail and event bodies would match Lookout (and Parula's custom colors).
8. **Optional housekeeping:** add `<copied to="…lookout/…">` markers in the frontend originals of the 121 copied blocks (69 Lookout files). Then a change there shows that Lookout has a copy. This touches many frontend files, so it's best done whenever a file is touched anyway.

Not recommended: a theme rewrite, or moving Lookout's own components to the classic variables. Mapping `--lo-*` onto the classic variables in one place is the right approach. frontend/ just needs a few more theme variables (accent, secondary text) instead of hard-coded values, `:global(.lookout)` rules where a single component needs a different shape, and generic class names like `nav-list` and `nav-entry` where several lists share one look.
