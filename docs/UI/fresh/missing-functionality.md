# Fresh: Missing functionality

The Fresh design asks for some functions that Parula doesn't have yet. Fresh doesn't build them, because it adds no new functionality and doesn't change `logic/`. This page lists them.

Each entry says what is missing, where it would go in Fresh, and why it's missing. Every entry was checked against the code: the classic frontend doesn't offer it either, or offers it only as an empty placeholder. Paths are relative to `app/`.

Web apps and Topic: nothing missing. Fresh restyles the classic components there.

## Window and navigation

- **Keyboard access to the app bar.** Where: the app and sub-app buttons in the app bar. Why: `frontend/AppsBar/AppButton.svelte` and `SubAppButton.svelte` are boxes with a click handler, not buttons, so they can't get the keyboard focus. Classic has no keyboard access there either.
- **Closing a sub-app from the app bar.** Where: the rows of open composers and events under Mail and Calendar. Why: classic `SubAppButton` has no close action and no middle-click. Composers and events close from inside their page.
- **Several notifications at once.** Where: the banner under the top bar. Why: classic `frontend/MainWindow/NotificationBar.svelte` shows only the first notification. It sorts by the severity names alphabetically, so "meltdown" ranks below "error" and "warning" below "info". That looks like a bug in classic. Fresh uses the same logic.
- **Unread count on the Mail app.** Where: a badge on Mail in the app bar. Why: `MustangApp` has no count, and classic shows none.
- **Keyboard shortcut to the search field.** Where: the search field in the top bar. Why: classic has no such shortcut.
- **Own windows for a message, a composer or an event.** Where: a window with the top bar and the same page, without the app bar. Why: Parula has no secondary windows. A message opens in the reader, composers and events open as sub-apps in the main window.

## Mail

- **Save all attachments.** Where: at the end of the attachments row in the reader. Why: classic `frontend/Mail/Message/AttachmentsUI.svelte` has no such action. Each attachment has Save as in its own menu.
- **Open or close a folder in the tree without selecting it.** Where: the arrows in the folder tree. Why: the toggle in `frontend/Shared/FastTreeItem.svelte` is switched off, so the tree opens only the path to the selected folder. In Fresh, the arrow shows the state, and a click selects the folder, as in classic.
- **Sorting the message list.** Where: the column headers of the table list. Why: classic message lists are always sorted by date, and `FastList` columns have no sorting.

## Composer

- **Reply-To field.** Where: the recipients, under Bcc. Why: `EMail.replyTo` exists in `logic/`, but the classic composer has no field for it. Fresh reuses the classic composer.
- **Choosing a signature per mail.** Where: the composer toolbar. Why: the classic composer has no signature control. `logic/Mail/ComposeActions.ts` adds the identity's signature from the account settings when sending.
- **Remove button on recipients.** Where: the To, Cc and Bcc entries. Why: `frontend/Contacts/PersonAutocomplete/PersonEntry.svelte` has none. A click on the entry opens the person popup with Remove, as in classic.
- **Invalid addresses marked in the recipients.** Where: the To, Cc and Bcc entries. Why: the entry doesn't know whether an address is valid. Classic only shows a notification for no-reply addresses when the composer opens.
- **GIF and sticker pickers.** Where: the emoji panel. Why: `frontend/Chat/Emoji/GIFPicker.svelte` and `StickerPicker.svelte` are empty in classic, and their buttons do nothing.

## Calendar

- **Moving and resizing events with the mouse.** Where: the day, week and month grids. Why: classic has no drag or resize of events, only double-click to create and the time fields in the editor. `logic/` has nothing for it either.
- **Keyboard navigation in the grids.** Where: the day, week and month grids (arrow keys between days and events, Enter opens). Why: the classic grids are mouse-only. Only the list view has keys.
- **Today button in the month and 4-week views.** Where: the grid header. Why: classic has "Go back to today" only in the day and week views.
- **Week number and a title with the day range** ("26 Oct – 1 Nov 2026"). Where: the grid header. Why: classic `DateRange` shows only month and year, and `logic/util/date.ts` has no week number function.
- **Weekend days in a different shade.** Where: the day, week and month grids. Why: there is no weekend in `logic/` or the classic frontend. Weeks always start on Monday, and which days are the weekend depends on the country.
- **Days of other months in a different shade.** Where: the month view. Why: classic `frontend/Calendar/MonthView/DayCell.svelte` and `DayLabel.svelte` don't know which month the view shows.
- **List view grouped by day.** Where: the list view and the search results, with a header per day. Why: classic `ListView` is a flat `FastList` with a day column, and `FastList` has no group rows.
- **Small month calendar for navigation.** Where: the calendar column, above the calendar list. Why: the classic desktop calendar has only previous, next, Today and the range title. There is no month picker.
- **Moving an event to another calendar.** Where: a calendar chooser in the event editor header. Why: in classic `frontend/Calendar/EditEvent/DialogHeader.svelte` the chooser is commented out ("Moving events has too many bugs. #1277"). Moving needs fixes in `logic/` first.

## Contacts

- **Avatar with initials.** Where: wherever a person shows: reader header, person list, person page, chat. Why: `frontend/Contacts/Person/PersonPicture.svelte` shows only a picture, an icon or an empty placeholder. Initials and a colour per name would be new. Fresh shows the picture when there is one.
- **New group.** Where: the New contact menu or the address book column. Why: `Addressbook.newGroup()` exists in `logic/`, but no classic desktop screen calls it, and a selected group shows no page. Only Lookout has a group form.
- **Cancel while editing a person.** Where: the person page header, next to Save. Why: classic `frontend/Contacts/PersonPage/NameBox.svelte` has only Save. The fields change the person directly, so there is nothing to go back to.
- **Preferences** (preferred way to reach the person, notifications). Where: the person page. Why: the box is commented out in classic `frontend/Contacts/PersonPage/ContactBoxes.svelte`, and there is no logic behind it.
- **Opening a chat from the contact history.** Where: the chat entries in the person's history. Why: `onOpen()` in classic `frontend/Contacts/History/ChatLog.svelte` is a TODO (`message.chat` doesn't exist).

## Chat

- **Unread count per room.** Where: the room list. Why: `logic/Chat/ChatRoom.ts` has no unread count. Messages have `isRead`, but nothing counts them per room.
- **Reply to and forward a chat message.** Where: the hover bar of a message. Why: classic `frontend/Chat/MessageView/ActionBar.svelte` shows both buttons, but `onReply()` and `onForward()` do nothing.
- **Creating a chat room.** Where: the New chat menu. Why: classic `frontend/Chat/Header.svelte` opens nothing for "Create new chat room". The dialog is an empty block.

## Files

- **Download a file.** Where: the toolbar of the details pane. Why: classic `frontend/Files/RightSidePane/ActionToolbar.svelte` has Copy link, Share, Move and Delete, but no Download.
- **Share and move a file.** Where: the same toolbar. Why: the buttons are there in classic, but disabled ("Not yet implemented").
- **Recent files.** Where: Recent in the files column. Why: classic `frontend/Files/LeftPane/RecentList.svelte` is a TODO, and its list is always empty.
- **Tag filter and file search.** Where: Tags and Search in the files column. Why: classic `frontend/Files/FolderLeftPane/TagsList.svelte` has a TODO instead of the search, and `SearchFile.startSearch()` in `logic/` has no implementation.
- **Upload progress.** Where: the details pane or the banner. Why: classic shows none, and `Directory.addFile()` reports no progress.

## Meet

- **Notes during a call.** Where: a Notes tab next to the participants in the call sidebar. Why: `MeetingNotes` is commented out in classic `frontend/Meet/ParticipantsBar/Sidebar.svelte`.
- **Call history.** Where: the Meet start page. Why: classic `frontend/Meet/Start/CallHistory.svelte` is a "TODO" placeholder. The start page lists previous meetings from the calendar instead.

## Settings

- **Overview page for the main categories.** Where: the page for General, Mail, Calendar and the other main categories. Why: the main categories have no page in `frontend/Settings/SettingsCategories.ts`. Classic shows an empty page there too. Fresh shows the page header with the category name.
- **Page descriptions.** Where: under the page title. Why: `SettingsCategory.description` is empty for every category. Fresh shows it as soon as a category has one.

## Setup

- **"Setup" as the top bar title.** Where: the top bar while a setup page is open. Why: setup pages are opened with `goTo()`, not as an app, so the top bar keeps the title of the previous app (Mail or Settings), in classic too.

## Controls

- **Keyboard access to switches.** Where: the switches in Settings (`frontend/Shared/Checkbox.svelte` with `toggle`). Why: in this mode the classic checkbox has no focusable element, so a switch can't be reached or changed with the keyboard. Fresh only restyles it.

## Design points not done

Here the function exists in Fresh, but the Fresh design wanted a different look or an extra place to reach it. Each one would need new markup or new strings in a classic component, or a copy of it.

Window and navigation
- Arrow on the workspace button in the top bar: the reused `frontend/MainWindow/WorkspaceHeader.svelte` has none, and adding one would change classic.
- The user's Background colour on the top bar: CSS can't tell a colour the user set from the default, so the top bar follows the Left bar colour.
- "More info about this error" as a text button in the banner: Fresh reuses the classic banner, which has an icon button with the same tooltip.
- A search placeholder per app ("Search mail"): needs new strings and a change in the classic window header.
- An own tooltip component: Fresh uses the native tooltips, like classic.

Controls
- Shortcut text at the end of menu items: classic `frontend/Shared/Menu/MenuItem.svelte` shows the shortcut only in the tooltip.
- Check mark on the chosen menu item: `MenuItem` has only a selected state, which Fresh shows as a tinted row.
- Toolbar groups with dividers, and hiding commands by priority when narrow: classic `frontend/Shared/Toolbar/Toolbar.svelte` is a plain row that wraps.
- An error state with a message under a text field: no classic input has one. The pages show their errors separately.
- A progress bar without a known total: classic `frontend/Shared/ProgressBar.svelte` always needs a value and a maximum.

Mail
- The unread count in the message list header ("12 unread · 340"): Fresh shows classic's count texts. The unread version needs a new string.

Composer (Fresh reuses the classic composer)
- The subject stays under the editor toolbar, not above it.
- No "From" label and no sender name when there is only one identity.
- The classic loading spinner.
- Attachments in the side pane, not as chips under the text.
- Close is the classic X with its Save and Discard menu, not a labeled button.
- One encryption button with a menu, not separate Encrypt and Sign switches.

Calendar
- The event headers keep the classic icon buttons for Edit, Save and Cancel, with the labels as tooltips. Labels would need a copy of their save logic.
- The calendar column is closed at start, as in classic, because its state is shared with classic. Fresh always shows the button that opens it.

Contacts
- "3 selected" in the selection bar: needs a new string in classic `frontend/Contacts/PersonsActionToolbar.svelte`.
- A labeled "Write mail" button on the person page: classic `frontend/Contacts/PersonPage/CallButtons.svelte` has icon buttons.

Chat
- A drop-down to choose the account in the room column: Fresh restyles classic `frontend/Shared/AccountSelectorRound.svelte` as a row of account buttons.
- "Select a conversation" while no room is open: classic `frontend/Chat/ChatAppD.svelte` shows nothing there.

Files
- A More menu in the folder header: classic has the folder commands only in the context menu of the folder tree.
- Download, share and delete on hover in the file rows: classic has these actions only in the details pane.
- A drawn folder icon: Fresh recolours classic's folder emoji with CSS instead of changing the markup.
- A message while no folder is selected: classic `frontend/Files/FilesAppD.svelte` shows nothing there.

Meet
- Labeled Start, Plan and Phone call buttons at the top of the start page: classic `frontend/Meet/Start/StartScreen.svelte` has icon buttons with tooltips and one labeled "Start a new meeting" in the middle.
- An outline around the video of the person speaking: classic `frontend/Meet/View/Video/VideoWithLabel.svelte` has no speaking state on the video. The microphone icon next to the name shows it.

Settings
- Fresh's own colour choices for accounts and workspaces: the colour list is in `logic/Abstract/Workspace.ts` (`accountColors`, including a pastel pink), which Fresh doesn't change.

Setup
- Labels above the email and password fields: classic has only placeholders. Labels would be new strings.
- Icons and a one-line description on the account type buttons: new content in classic `frontend/Setup/SetupAnyAccountType.svelte`.
