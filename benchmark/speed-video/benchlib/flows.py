"""Account setup flows (T1) that find their way through each app's own setup by asking the app's probe what is
shown, and act like a user at the elements' screen positions. Every input is logged and counted (phase "step");
inputs that only exist because of the benchmark (phase "prepare") are logged, not counted, and disclosed."""

import time

from .probe import AppProbe, ProbeError
from .scenario import Action, Step


class FlowError(Exception):
    pass


class FlowContext:
    def __init__(self, driver, probe: AppProbe, options: dict, final_checks: dict):
        self.driver = driver
        self.probe = probe
        self.options = options
        self.final_checks = dict(final_checks or {})
        self.path: list[str] = []
        self.variables = driver.variables
        self.step_names: list[str] = []

    def note(self, text: str):
        self.path.append(text)
        self.driver.log.write("flow", note=text)

    def value(self, name: str) -> str:
        return self.variables.values.get(name, "")

    @staticmethod
    def action(kind: str, arg=None, **options) -> Action:
        return Action(kind, arg, options)

    def act(self, *actions: Action):
        self.driver.do_actions(list(actions), "step")

    def prepare(self, *actions: Action):
        self.driver.do_actions(list(actions), "prepare")

    def finish(self, *actions: Action):
        self.driver.do_actions(list(actions), "finish")

    def final_step_checks(self) -> dict:
        checks = {"complete": self.final_checks.get("complete"),
                  "verify_probe": bool(self.final_checks.get("verify", False)),
                  "after_end": str(self.final_checks.get("after_end", "report")),
                  "first_visible_list": bool(self.final_checks.get("first_visible", False))}
        if self.final_checks.get("settle"):
            checks["settle"] = dict(self.final_checks["settle"])
        return checks

    def step(self, name: str, *actions: Action, until: set[str] | None = None, fail: tuple[str, ...] = ("error:",),
             final: bool = False, settle: dict | None = None, final_pages: set[str] | None = None) -> Step:
        """A measured step: its last action starts the timer, which runs until the screen settles at the moment the
        app shows one of the pages `until` (asked only while the screen is quiet; the time comes from the
        recording). `final`: until the Inbox lists all messages, then the completeness check. `final_pages`: pages
        on which the step turns into the final one (an app that opens its Inbox without a last page)."""
        repeated = self.step_names.count(name)
        self.step_names.append(name)
        if repeated:
            name = f"{name}-{repeated + 1}"
        step = Step(name, list(actions), True, dict(settle or {}), "none")
        if until:
            step.complete = {"pages": sorted(until), "fail": list(fail)}
        if final_pages:
            step.becomes_final = {"pages": sorted(final_pages), "checks": self.final_step_checks()}
        if final:
            checks = self.final_step_checks()
            step.complete = checks["complete"]
            step.verify_probe = checks["verify_probe"]
            step.after_end = checks["after_end"]
            step.first_visible_list = checks["first_visible_list"]
            if checks.get("settle"):
                step.settle = {**checks["settle"], **step.settle}
        self.driver.run_step(step)
        return step

    def page(self, expected: set[str], timeout_s: float = 60) -> str:
        try:
            return self.probe.wait_page(expected, timeout_s, on_interruption=self.dismiss)
        except ProbeError as ex:
            raise FlowError(str(ex)) from ex

    def dismiss(self, element: str):
        """A first-run dialog the app shows in between (e.g. a privacy notice): closed with its own button, not
        counted, listed in the flow path."""
        self.note(f"closed the app's notice with '{element}' (not counted)")
        self.prepare(self.action("click", element))

    def replace_text(self, element: str, text: str):
        """Click into a field, select its content and type the new text (3 user actions)."""
        self.act(self.action("click", element), self.action("key", "ctrl+a"), self.action("type", text))

    def type_into(self, element: str, text: str):
        """Type into a field; a click into it first unless the app already put the cursor there."""
        found = self.probe.find(element)
        if not (found and found.get("focused")):
            self.act(self.action("click", element))
        self.act(self.action("type", text))

    def field_value(self, element: str) -> str | None:
        found = self.probe.find(element)
        return None if found is None else found.get("value")

    def other_server(self) -> list[str] | None:
        """None if the configuration the app found names only the account's server, else the host names it names
        (empty if unreadable): the flow then corrects them in the app's manual setup, like a user, and the
        password never goes to another server."""
        hosts = self.probe.found_hosts()
        own = {self.value("server.imap_host").lower(), self.value("server.smtp_host").lower()}
        return None if hosts and set(hosts) <= own else hosts


class ParulaSetupFlow:
    """Parula's own setup: e-mail address and password, then the configuration it finds (autoconfig) or, if it
    finds none, its manual setup. Parula 0.9.39 doesn't discover JMAP (Stalwart's autoconfig lists IMAP, POP3 and
    SMTP), so its JMAP account always goes through the manual setup with protocol "JMAP". Its setup pages play a
    background video, which keeps playing (the probe reports where it is visible, and the settle detection leaves
    that area out)."""

    def __init__(self, ctx: FlowContext):
        self.ctx = ctx
        self.protocol = str(ctx.options.get("protocol", "jmap")).lower()

    def run(self):
        ctx, a = self.ctx, FlowContext.action
        manual_pages = {"manual", "manual-full", "error:manual", "error:manual-full"}
        page = ctx.page({"initial", "email", "import-accounts", "import-addressbooks"}, 120)
        if page == "import-accounts":
            ctx.note("Parula offered to import Thunderbird accounts of this computer's user: skipped")
            ctx.step("skip-import", a("click", "setup.skip"), until={"import-addressbooks", "initial"}, fail=())
            page = ctx.page({"import-addressbooks", "initial"}, 30)
        if page == "import-addressbooks":
            ctx.note("Parula offered to import Thunderbird address books: skipped")
            ctx.step("skip-addressbooks", a("click", "setup.skip"), until={"initial"}, fail=())
            page = ctx.page({"initial"}, 30)
        if page == "initial":
            ctx.act(a("click", "setup.add_email"))
            ctx.page({"email"}, 30)
        ctx.type_into("setup.email", "${account.email}")
        ctx.act(a("key", "Return"), a("type", "${account.password}"))
        ctx.step("find-config", a("key", "Return"), until={"found", "finalize"} | manual_pages, fail=())
        page = ctx.page({"found", "finalize"} | manual_pages, 30)
        if page == "found":
            ctx.note("configuration found by the app (autoconfig)")
            if self.protocol == "imap" or self.offers_protocol():
                self.choose_found_option()
                hosts = ctx.other_server()
                if hosts is None:
                    ctx.step("check-config", a("click", "setup.next"), until={"finalize"})
                else:
                    ctx.note(f"the found configuration names another server ({', '.join(hosts) or 'unreadable'}): "
                             "manual setup")
                    ctx.step("manual-setup", a("click", "setup.manual"), until=manual_pages, fail=())
                    page = ctx.page(manual_pages, 30)
            else:
                ctx.note("the found configuration offers no JMAP: manual setup")
                ctx.step("manual-setup", a("click", "setup.manual"), until=manual_pages, fail=())
                page = ctx.page(manual_pages, 30)
        if page in manual_pages:
            if not any("manual setup" in note for note in ctx.path):
                ctx.note("no configuration found: manual setup")
            self.manual(page.removeprefix("error:"))
        page = ctx.page({"finalize", "error:manual", "error:manual-full", "error:found"}, 30)
        if page != "finalize":
            raise FlowError(f"Parula's setup didn't accept the configuration: {ctx.probe.page_text()[:400]}")
        ctx.step("open-inbox", a("click", "setup.next"), final=True)

    def offers_protocol(self) -> bool:
        self.ctx.probe.values["protocol"] = self.protocol
        return self.ctx.probe.find("found.option") is not None

    def choose_found_option(self):
        """Selects the protocol among the found configurations, unless it is already the selected one."""
        ctx = self.ctx
        ctx.probe.values["protocol"] = self.protocol
        option = ctx.probe.find("found.option")
        if option is not None and not option.get("checked"):
            ctx.act(FlowContext.action("click", "found.option"))
            deadline = time.monotonic() + 5
            while not (ctx.probe.find("found.option") or {}).get("checked") and time.monotonic() < deadline:
                time.sleep(0.1)

    def manual(self, page: str):
        ctx, a = self.ctx, FlowContext.action
        if self.protocol == "jmap":
            ctx.act(a("click", "manual.protocol"), a("key", "j"), a("key", "Return"))
            url = ctx.value("server.jmap_url")
            if ctx.field_value("manual.url") != url:
                ctx.replace_text("manual.url", "${server.jmap_url}")
                ctx.note("typed the JMAP URL")
            if page == "manual":
                ctx.step("show-details", a("click", "setup.next"), until={"manual-full"})
        else:
            for element, variable in (("manual.incoming_host", "server.imap_host"),
                                      ("manual.outgoing_host", "server.smtp_host")):
                if ctx.field_value(element) != ctx.value(variable):
                    ctx.replace_text(element, "${" + variable + "}")
            if page == "manual":
                ctx.step("show-details", a("click", "setup.next"), until={"manual-full"})
            for element, variable in (("manual.incoming_port", "server.imap_port"),
                                      ("manual.outgoing_port", "server.smtp_port")):
                if ctx.field_value(element) != ctx.value(variable):
                    ctx.replace_text(element, "${" + variable + "}")
                    ctx.note(f"changed {element.split('.')[1].replace('_', ' ')} to the server's port")
        ctx.step("check-config", a("click", "setup.next"), until={"finalize"})


class ThunderbirdSetupFlow:
    """Thunderbird's Account Hub: name and e-mail address, the configuration it finds (autoconfig, ISPDB) or its
    manual configuration, the password, then its own way to the Inbox."""

    def __init__(self, ctx: FlowContext):
        self.ctx = ctx

    def run(self):
        ctx, a = self.ctx, FlowContext.action
        manual_pages = {"manual", "manual:info", "manual:warning", "manual:success"}
        ctx.page({"email"}, 120)
        ctx.act(a("click", "hub.realName"), a("type", "${account.name}"), a("click", "hub.email"),
                a("type", "${account.email}"))
        ctx.step("find-config", a("click", "hub.forward"),
                 until={"found", "protocol-select", "password"} | manual_pages)
        page = ctx.page({"found", "protocol-select", "password"} | manual_pages, 30)
        hosts = ctx.other_server() if page == "found" else None
        if page == "found" and hosts is None:
            ctx.note("configuration found by the app (autoconfig)")
            ctx.step("use-config", a("click", "hub.forward"), until={"password"})
        elif page == "found":
            ctx.note(f"the configuration Thunderbird found names another server ({', '.join(hosts) or 'unreadable'}): "
                     "manual configuration")
            ctx.step("edit-config", a("click", "hub.edit"), until=manual_pages)
            self.connect_manually()
        elif page == "protocol-select" or page in manual_pages:
            ctx.note("no complete configuration found: manual configuration")
            if page == "protocol-select":
                ctx.step("choose-imap", a("click", "hub.forward"), until=manual_pages)
            self.connect_manually()
        ctx.page({"password"}, 30)
        ctx.act(a("click", "hub.password"), a("type", "${account.password}"))
        ctx.step("create-account", a("key", "Return"), until={"sync", "success"})
        page = ctx.page({"sync", "success"}, 30)
        if page == "sync":
            ctx.step("sync-accounts", a("click", "hub.forward"), until={"success"})
        ctx.step("finish", a("click", "hub.forward"), until={"mail", "inbox"})
        page = ctx.page({"mail", "inbox"}, 30)
        if page == "inbox":
            raise FlowError("Thunderbird opened the Inbox by itself; the final step needs the completion checks")
        ctx.step("open-inbox", a("click", "folder.inbox"), final=True)

    def connect_manually(self):
        ctx, a = self.ctx, FlowContext.action
        self.manual()
        ctx.step("connect", a("click", "hub.forward"), until={"manual:success", "password", "found"})
        page = ctx.page({"manual:success", "password", "found"}, 30)
        if page == "manual:success":
            ctx.note("Thunderbird completed the settings; Connect again")
            ctx.step("connect-again", a("click", "hub.forward"), until={"password", "found"})
            page = ctx.page({"password", "found"}, 30)
        if page == "found":
            if ctx.other_server() is not None:
                raise FlowError(f"Thunderbird's configuration names another server after the manual configuration: "
                                f"{ctx.probe.found_hosts()}")
            ctx.step("use-config", a("click", "hub.forward"), until={"password"})

    def manual(self):
        """Fields in their tab order; a field scrolled out of the form's view is reached with Tab, like a user would."""
        ctx, a = self.ctx, FlowContext.action
        for element, variable in (("manual.incoming_host", "server.imap_host"),
                                  ("manual.incoming_port", "server.imap_port"),
                                  ("manual.outgoing_host", "server.smtp_host"),
                                  ("manual.outgoing_port", "server.smtp_port")):
            if ctx.field_value(element) == ctx.value(variable):
                continue
            found = ctx.probe.find(element)
            if found is not None and found.get("hit"):
                ctx.replace_text(element, "${" + variable + "}")
                continue
            for _ in range(10):
                if ctx.probe.focused(element):
                    break
                ctx.act(a("key", "Tab"))
            else:
                raise FlowError(f"Couldn't reach {element} with Tab")
            ctx.act(a("key", "ctrl+a"), a("type", "${" + variable + "}"))


class OutlookClassicSetupFlow:
    """Outlook (classic), started with an empty profile: its own "Add account" dialog, the default way (no
    "set up manually" option); the pages that follow depend on what Outlook detects for the address."""

    def __init__(self, ctx: FlowContext):
        self.ctx = ctx

    def run(self):
        ctx, a = self.ctx, FlowContext.action
        after_connect = {"advanced-setup", "imap-settings", "password", "done", "error"}
        ctx.page({"account-email"}, 180)
        ctx.type_into("field.email", "${account.email}")
        ctx.step("connect", a("click", "button.connect"), until=after_connect, fail=())
        for _ in range(6):
            page = ctx.page(after_connect, 30)
            ctx.note(page)
            if page == "error":
                raise FlowError(f"Outlook reports an error in its account setup: {ctx.probe.page_text()[:400]}")
            if page == "advanced-setup":
                ctx.step("choose-imap", a("click", "tile.imap"), until={"imap-settings", "password", "error"}, fail=())
            elif page == "imap-settings":
                ctx.step("imap-settings", a("click", "button.next"), until={"password", "done", "error"}, fail=())
            elif page == "password":
                ctx.type_into("field.password", "${account.password}")
                ctx.step("login", a("click", "button.connect"), until={"done", "error", "imap-settings"}, fail=())
            elif page == "done":
                mobile = ctx.probe.find("checkbox.mobile")
                if mobile is not None and mobile.get("checked"):
                    ctx.note("unchecked 'Set up Outlook Mobile on my phone, too'")
                    ctx.act(a("click", "checkbox.mobile"))
                ctx.step("open-inbox", a("click", "button.done"), final=True)
                return
        raise FlowError("Outlook's account setup didn't reach its last page")


class NewOutlookSetupFlow:
    """New Outlook for Windows: its own "Add account" flow for an IMAP address, which ends with its notice that the
    account is synced through the Microsoft Cloud."""

    def __init__(self, ctx: FlowContext):
        self.ctx = ctx

    def run(self):
        ctx, a = self.ctx, FlowContext.action
        after_continue = {"choose-provider", "imap-form", "cloud-sync", "success", "mail"}
        page = ctx.page({"add-account", "mail"}, 180)
        if page == "mail":
            raise FlowError("New Outlook already has an account; the test needs it without accounts (the previous "
                            "run's account wasn't removed, or this Windows user has accounts there)")
        ctx.type_into("field.email", "${account.email}")
        step = ctx.step("continue", a("click", "button.continue"), until=after_continue - {"mail"},
                        final_pages={"mail"}, fail=())
        for _ in range(6):
            if step.final_reached:
                return
            page = ctx.page(after_continue, 60)
            ctx.note(page)
            if page == "choose-provider":
                step = ctx.step("choose-imap", a("click", "option.imap"), until={"imap-form", "cloud-sync"}, fail=())
            elif page == "imap-form":
                ctx.type_into("field.password", "${account.password}")
                step = ctx.step("connect", a("click", "button.continue"), until={"cloud-sync", "success"},
                                final_pages={"mail"}, fail=())
            elif page == "cloud-sync":
                step = ctx.step("cloud-sync", a("click", "button.continue"), until={"success"},
                                final_pages={"mail"}, fail=())
            elif page == "success":
                ctx.step("open-inbox", a("click", "button.done"), final=True)
                return
            else:
                raise FlowError("New Outlook shows its mail view, but no step measured the Inbox listing")
        raise FlowError("New Outlook's account setup didn't reach its last page")


class NewOutlookRemoval:
    """After a run: Settings → Accounts → Your accounts → Manage (the test account's row) → Remove → "Remove from
    all devices" (also from the Microsoft Cloud, which Microsoft names as the way to delete the stored credentials).
    Not measured, not user actions (phase "finish")."""

    def __init__(self, ctx: FlowContext, email: str):
        self.ctx = ctx
        self.email = email

    def run(self, wait_gone_s: float = 120):
        ctx, a = self.ctx, FlowContext.action
        ctx.probe.values["account"] = self.email
        ctx.finish(a("click", "button.settings"), a("click", "nav.accounts"))
        if ctx.probe.find("nav.email_accounts") is not None:
            ctx.finish(a("click", "nav.email_accounts"))
        ctx.finish(a("click", "button.manage"), a("click", "button.remove"), a("click", "option.remove_all_devices"))
        if ctx.probe.find("button.confirm") is not None:
            ctx.finish(a("click", "button.confirm"))
        deadline = time.monotonic() + wait_gone_s
        while time.monotonic() < deadline:
            if self.email.lower() not in ctx.probe.page_text().lower():
                ctx.driver.log.write("account_removed", email_domain=self.email.rpartition("@")[2])
                return
            time.sleep(2)
        raise FlowError(f"New Outlook still lists the test account {wait_gone_s:.0f} s after its removal")


class Flows:
    known = {"parula-setup": ParulaSetupFlow, "thunderbird-setup": ThunderbirdSetupFlow,
             "outlook-classic-setup": OutlookClassicSetupFlow, "outlook-new-setup": NewOutlookSetupFlow}

    @classmethod
    def run(cls, spec: dict, driver, probe: AppProbe, final_checks: dict) -> list[str]:
        name = spec.get("name")
        if name not in cls.known:
            raise FlowError(f"Unknown flow '{name}'. Known: {', '.join(cls.known)}")
        ctx = FlowContext(driver, probe, spec, final_checks)
        cls.known[name](ctx).run()
        return ctx.path
