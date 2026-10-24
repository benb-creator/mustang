class SessionNotes:
    """What a session changed on the computer or found before its runs, listed with the deviations (manifest.json,
    report, method texts). Every note is one of `templates` with its {placeholders} filled in; translations/<lang>.yaml
    has each template with the same placeholders, so a note with variable text is translated too."""

    templates = {
        "power_plan_set": "Power plan: High performance for the session (was {plan})",
        "power_plan_unchanged": "Power plan: unchanged ({plan})",
        "power_plan_unknown": "Power plan: unchanged (the active plan couldn't be read)",
        "toasts_off": "Windows notifications (toasts) off for the session",
        "awake": "Sleep and display timeout suspended while the session runs",
        "parula_profile_aside": "Parula: the computer user's Parula profile was moved aside for the session and moved "
                                "back afterwards ({count} folders)",
        "parula_updates_off": "Parula: its update check was off for the session (resources/app-update.yml renamed), "
                              "like the Linux .deb, which has none",
        "outlook_profile": "Outlook (classic): started with its own profile '{profile}' (/profile), which holds only "
                           "the test account and is deleted after every run",
        "open_apps": "Windows: other apps were open during the session: {apps}",
        "server_guard": "Server check: before the session, {sources} named {hosts} for the address's domain, not "
                        "only the account's server {server}. Each app's setup therefore read the server it found before "
                        "the password and corrected another one in the app's own manual setup, as a user would (counted "
                        "as user actions); an app that shows its servers only behind a button had it opened to read "
                        "them (not counted)",
        "server_guard_unchecked": "Server check: before the session, {sources} couldn't be checked for the "
                                  "address's domain. Each app's setup therefore read the server it found before the "
                                  "password and corrected another one in the app's own manual setup, as a user would "
                                  "(counted as user actions); an app that shows its servers only behind a button had "
                                  "it opened to read them (not counted)",
    }

    def __init__(self):
        self.lines: list[str] = []

    def add(self, name: str, **values):
        self.lines.append(self.templates[name].format(**values))

    def extend(self, notes: "SessionNotes"):
        self.lines += notes.lines

    def __iter__(self):
        return iter(self.lines)

    def __len__(self):
        return len(self.lines)
