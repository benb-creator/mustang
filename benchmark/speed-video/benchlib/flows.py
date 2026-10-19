"""Account setup flows (T1) that find their way through each app's own setup by asking the app's probe what is
shown, and act like a user at the elements' screen positions. Every input is logged and counted (phase "step");
inputs that only exist because of the benchmark (phase "prepare") are logged, not counted, and disclosed."""

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

    def step(self, name: str, *actions: Action, until: set[str] | None = None, fail: tuple[str, ...] = ("error:",),
             final: bool = False, settle: dict | None = None):
        """A measured step: its last action starts the timer, which runs until the screen settles at the moment the
        app shows one of the pages `until` (asked only while the screen is quiet; the time comes from the
        recording). `final`: until the Inbox lists all messages, then the completeness check."""
        step = Step(name, list(actions), True, dict(settle or {}), "none")
        if until:
            step.complete = {"pages": sorted(until), "fail": list(fail)}
        if final:
            step.complete = self.final_checks.get("complete")
            step.verify_probe = bool(self.final_checks.get("verify", False))
            step.after_end = str(self.final_checks.get("after_end", "report"))
            step.first_visible_list = bool(self.final_checks.get("first_visible", False))
            if self.final_checks.get("settle"):
                step.settle = {**self.final_checks["settle"], **step.settle}
        self.driver.run_step(step)

    def page(self, expected: set[str], timeout_s: float = 60) -> str:
        try:
            return self.probe.wait_page(expected, timeout_s)
        except ProbeError as ex:
            raise FlowError(str(ex)) from ex

    def replace_text(self, element: str, text: str):
        """Click into a field, select its content and type the new text (3 user actions)."""
        self.act(self.action("click", element), self.action("key", "ctrl+a"), self.action("type", text))

    def field_value(self, element: str) -> str | None:
        found = self.probe.find(element)
        return None if found is None else found.get("value")


class ParulaSetupFlow:
    """Parula's own setup: e-mail address and password, then the configuration it finds (autoconfig) or, if it
    finds none, its manual setup. Parula 0.9.39 doesn't discover JMAP (Stalwart's autoconfig lists IMAP, POP3 and
    SMTP), so its JMAP account always goes through the manual setup with protocol "JMAP"."""

    def __init__(self, ctx: FlowContext):
        self.ctx = ctx
        self.protocol = str(ctx.options.get("protocol", "jmap")).lower()

    def run(self):
        ctx, a = self.ctx, FlowContext.action
        manual_pages = {"manual", "manual-full", "error:manual", "error:manual-full"}
        page = ctx.page({"initial", "email"}, 120)
        if page == "initial":
            ctx.act(a("click", "setup.add_email"))
            ctx.page({"email"}, 30)
        if ctx.probe.find("setup.pause_video"):
            ctx.prepare(a("click", "setup.pause_video"), a("click", "setup.email"))
            ctx.note("paused the setup screen's background video with its own Pause button (not counted)")
        ctx.act(a("type", "${account.email}"), a("key", "Return"), a("type", "${account.password}"))
        ctx.step("find-config", a("key", "Return"), until={"found", "finalize"} | manual_pages, fail=())
        page = ctx.page({"found", "finalize"} | manual_pages, 30)
        if page == "found":
            ctx.note("configuration found by the app (autoconfig)")
            if self.protocol == "imap" or self.offers_protocol():
                self.choose_found_option()
                ctx.step("check-config", a("click", "setup.next"), until={"finalize"})
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
        if page == "found":
            ctx.note("configuration found by the app (autoconfig)")
            ctx.step("use-config", a("click", "hub.forward"), until={"password"})
        elif page == "protocol-select" or page in manual_pages:
            ctx.note("no complete configuration found: manual configuration")
            if page == "protocol-select":
                ctx.step("choose-imap", a("click", "hub.forward"), until=manual_pages)
            self.manual()
            ctx.step("connect", a("click", "hub.forward"), until={"manual:success", "password", "found"})
            page = ctx.page({"manual:success", "password", "found"}, 30)
            if page == "manual:success":
                ctx.note("Thunderbird completed the settings; Connect again")
                ctx.step("connect-again", a("click", "hub.forward"), until={"password", "found"})
                page = ctx.page({"password", "found"}, 30)
            if page == "found":
                ctx.step("use-config", a("click", "hub.forward"), until={"password"})
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


class Flows:
    known = {"parula-setup": ParulaSetupFlow, "thunderbird-setup": ThunderbirdSetupFlow}

    @classmethod
    def run(cls, spec: dict, driver, probe: AppProbe, final_checks: dict) -> list[str]:
        name = spec.get("name")
        if name not in cls.known:
            raise FlowError(f"Unknown flow '{name}'. Known: {', '.join(cls.known)}")
        ctx = FlowContext(driver, probe, spec, final_checks)
        cls.known[name](ctx).run()
        return ctx.path
