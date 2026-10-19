import time
from pathlib import Path

from .driver import EventLog, NoReaction, StepTimeout
from .scenario import Action


class FlowError(Exception):
    pass


class PointLocator:
    """Takes the place of the calibration for `ScenarioDriver.perform`: a click on an element name goes to where UI
    Automation found that element right before the click."""

    def __init__(self, region):
        self.region = region
        self.points: dict[str, tuple[int, int]] = {}

    def set(self, name: str, x: int, y: int):
        self.points[name] = (x, y)

    def absolute(self, point) -> tuple[int, int]:
        if isinstance(point, dict):
            return self.region.x + int(point["x"]), self.region.y + int(point["y"])
        if point not in self.points:
            raise FlowError(f"Element '{point}' wasn't located before the click")
        return self.points[point]

    def region_rects(self) -> dict:
        return {}


class WindowsFlowContext:
    """What a setup flow uses to act like a user: every key, typed text and click goes through the driver (logged as
    an input, counted as a user action). An action with `measure=<step>` starts a measured step: its timer runs
    from that input until the screen has settled and the probe confirms the expected page (`until`) or, for the
    final step, the complete Inbox listing."""

    def __init__(self, driver, probe, expected: dict, diagnostics: Path, quiet_s: float = 1.0,
                 step_timeout_s: float = 300, task_timeout_s: float = 7200, probe_interval_s: float = 2.0,
                 element_timeout_s: float = 60, no_reaction_s: float | None = 60, progress=print):
        self.driver = driver
        self.probe = probe
        self.expected = expected
        self.diagnostics = Path(diagnostics)
        self.quiet_s = quiet_s
        self.step_timeout_s = step_timeout_s
        self.task_timeout_s = task_timeout_s
        self.probe_interval_s = probe_interval_s
        self.element_timeout_s = element_timeout_s
        self.no_reaction_s = no_reaction_s
        self.progress = progress
        self.locator = PointLocator(driver.calibration.region)
        driver.calibration = self.locator
        self.steps: list[dict] = []
        self.flow_path: list[str] = []
        self.user_actions = 0
        self.prep_actions = 0
        self.pending: list[str] = []
        self.waited_s = 0.0
        self.final_done = False
        self.phase = "step"

    @property
    def log(self) -> EventLog:
        return self.driver.log

    def path(self, label: str):
        self.flow_path.append(label)
        self.log.write("flow_path", label=label)

    def locate(self, element: str, timeout_s: float | None = None):
        found = self.probe.element(element, self.element_timeout_s if timeout_s is None else timeout_s)
        if found is None:
            raise self.failure(f"Element '{element}' not found ({self.probe.map.query(element).describe()})")
        x, y = found.center
        self.locator.set(element, x, y)
        return found

    def failure(self, message: str) -> FlowError:
        name = f"flow-error-{len(self.steps) + 1}"
        try:
            self.probe.dump(self.diagnostics / f"{name}.json")
        except Exception as ex:
            message += f" (UI dump failed: {ex})"
        return FlowError(f"{message}; UI dump in {self.diagnostics / name}.txt")

    def perform(self, action: Action, measure: str | None = None, until: list[str] | None = None,
                final: bool = False, counted: bool = True):
        if measure and self.driver.marker is not None:
            self.driver.show_marker(f"step:{measure}")
        t_before = EventLog.now()
        t_after = self.driver.perform(action)
        phase = self.phase if counted else "prep"
        fields = {"phase": phase, "action": action.kind, "arg": self.driver.loggable_arg(action), "t_before": t_before}
        if measure:
            fields["step"] = measure
        self.log.write("input", t=t_after, **fields)
        if counted and self.phase == "step":
            self.user_actions += action.user_action_count
            self.pending.append(action.describe())
        elif not counted:
            self.prep_actions += 1
        if measure:
            self.log.write("step_start", t=t_after, step=measure, measure=True)
            self.wait(measure, t_after, until, final)
        return t_after

    def click(self, element: str, measure: str | None = None, until: list[str] | None = None, final: bool = False,
              counted: bool = True, timeout_s: float | None = None):
        self.locate(element, timeout_s)
        return self.perform(Action("click", element), measure, until, final, counted)

    def type(self, variable: str, into: str | None = None, measure: str | None = None,
             until: list[str] | None = None, final: bool = False):
        if into is not None:
            field = self.locate(into)
            if not field.focused:
                self.click(into)
        return self.perform(Action("type", "${" + variable + "}"), measure, until, final)

    def key(self, combo: str, measure: str | None = None, until: list[str] | None = None, final: bool = False,
            counted: bool = True):
        return self.perform(Action("key", combo), measure, until, final, counted)

    def page(self, pages: list[str] | None = None, timeout_s: float = 60) -> str:
        page, _ = self.probe.wait_page(pages, timeout_s, on_interruption=self.interruption)
        self.log.write("page", page=page, language=self.probe.language)
        if pages is not None and page not in pages:
            raise self.failure(f"Expected one of the pages {pages}, but the app shows '{page}'")
        return page

    def interruption(self, name: str, button):
        x, y = button.center
        self.locator.set(f"interruption.{name}", x, y)
        self.perform(Action("click", f"interruption.{name}"), counted=False)
        self.path(f"dismissed:{name}")

    def confirmed(self, step: str, until: list[str] | None, final: bool) -> tuple[bool, bool, dict]:
        """(confirmed, became_final, details): the expected page is shown, or the Inbox is completely listed."""
        if not final and until:
            page = self.probe.page()
            if page == "mail" and "mail" in until:
                final = True
            elif page in until:
                return True, False, {"page": page}
            else:
                return False, False, {"page": page}
        if final:
            listed = self.probe.inbox_listed(self.expected)
            return bool(listed.get("complete")), True, listed
        return True, False, {}

    def wait(self, step: str, since: float, until: list[str] | None, final: bool):
        live = self.driver.live
        limit = self.step_timeout_s if not final else max(0.0, self.task_timeout_s - self.waited_s)
        deadline = since + limit
        expect_change = True
        quiet = self.quiet_s
        cursor = since
        became_final = final
        while True:
            remaining = deadline - EventLog.now()
            if remaining <= 0:
                self.log.write("step_live_timeout", step=step, limit_s=limit)
                raise StepTimeout(step, limit)
            status, info = live.wait_settled(cursor, quiet, remaining, step, expect_change=expect_change,
                                             no_reaction_s=self.no_reaction_s if expect_change else None)
            self.log.write(f"step_live_{status.replace('-', '_')}", step=step, limit_s=limit, **info)
            if status == "timeout":
                raise StepTimeout(step, limit)
            if status == "no-reaction":
                raise NoReaction(f"Step '{step}': no screen change within {self.no_reaction_s:.0f} s after its "
                                 f"input (a missed click or key?)")
            ok, now_final, details = self.confirmed(step, until, became_final)
            became_final = became_final or now_final
            self.log.write("probe", step=step, final=became_final, **{**details, "complete": ok})
            if ok:
                still, still_info = live.wait_settled(EventLog.now(), quiet, quiet + 5, step, expect_change=False)
                if still_info.get("live_end") is None:
                    break
            cursor = EventLog.now()
            expect_change = False
            quiet = self.probe_interval_s if became_final else self.quiet_s
        ended = info.get("live_end") or EventLog.now()
        self.waited_s += max(0.0, ended - since)
        self.steps.append({"name": step, "actions": self.pending, "final": became_final})
        self.pending = []
        if became_final:
            self.final_done = True

    def summary(self) -> dict:
        return {"user_actions": self.user_actions, "prep_actions": self.prep_actions, "flow_path": self.flow_path,
                "steps": self.steps, "language": self.probe.language, "final_done": self.final_done}

    def verify(self) -> dict:
        self.phase = "verify"
        self.probe.inputs = VerifyInputs(self)
        try:
            return self.probe.verify(self.expected)
        finally:
            self.phase = "step"


class VerifyInputs:
    """Inputs of the check after the measured end: logged with phase "verify", not counted as user actions."""

    def __init__(self, ctx: WindowsFlowContext):
        self.ctx = ctx

    def click(self, x: int, y: int):
        self.ctx.locator.set("verify.target", x, y)
        self.ctx.perform(Action("click", "verify.target"))

    def key(self, combo: str):
        self.ctx.perform(Action("key", combo))


class SetupFlow:
    """One app's own account setup, from its first screen until the Inbox is listed (shared interface with the
    Linux flows in benchlib/flows.py: `run(ctx)`)."""

    app_kind = ""

    def run(self, ctx: WindowsFlowContext):
        raise NotImplementedError


class ParulaSetupFlow(SetupFlow):
    """Parula 0.9.39 with JMAP: the server's autoconfig offers no JMAP, so JMAP is set up through Parula's own
    "Manual setup" (protocol JMAP, the server's JMAP URL). Parula's setup pages play a background video, which never
    lets the screen settle: it is paused with its own Pause button (preparation, not a user action), and the click on
    "Add email address", which opens a page with a new video, is a user action without a measured wait (a local page
    switch); the email field gets its focus back after that pause, also as preparation."""

    app_kind = "parula"
    start_pages = ["import-accounts", "import-addressbooks", "first-account", "setup-mail"]

    def __init__(self, protocol: str = "jmap"):
        self.protocol = protocol

    @staticmethod
    def pause_video(ctx: WindowsFlowContext) -> bool:
        if ctx.probe.element("button.pause", timeout_s=3) is None:
            return False
        ctx.click("button.pause", counted=False)
        ctx.path("video-paused")
        return True

    def run(self, ctx: WindowsFlowContext):
        page = ctx.page(self.start_pages, timeout_s=120)
        self.pause_video(ctx)
        if page == "import-accounts":
            ctx.path("skip-import-accounts")
            ctx.click("button.skip", measure="skip-import", until=self.start_pages[1:])
            page = ctx.page(self.start_pages[1:])
        if page == "import-addressbooks":
            ctx.path("skip-import-addressbooks")
            ctx.click("button.skip", measure="skip-addressbooks", until=self.start_pages[2:])
            page = ctx.page(self.start_pages[2:])
        if page == "first-account":
            ctx.click("button.add_email")
            ctx.page(["setup-mail"])
            if self.pause_video(ctx):
                ctx.click("field.email", counted=False)
        ctx.type("account.email", into="field.email")
        ctx.key("Return")
        ctx.type("account.password", into="field.password")
        if self.protocol == "jmap":
            self.manual_jmap(ctx)
        else:
            ctx.key("Return", measure="find-config", until=["found-config", "no-config"])
            if ctx.page(["found-config", "no-config"]) == "no-config":
                raise ctx.failure("Parula found no configuration for the address")
            if ctx.probe.element("radio.imap", timeout_s=2) is not None:
                ctx.click("radio.imap")
            ctx.click("button.next", measure="check-login", until=["ready"])
        ctx.page(["ready"], timeout_s=30)
        ctx.click("button.next", measure="open-inbox", until=["mail"], final=True)

    def manual_jmap(self, ctx: WindowsFlowContext):
        ctx.path("manual-jmap")
        ctx.click("button.manual", measure="manual-setup", until=["manual", "manual-url"])
        if ctx.page(["manual", "manual-url"]) == "manual":
            ctx.click("combo.protocol")
            ctx.click("option.jmap", measure="choose-jmap", until=["manual-url"])
        ctx.type("server.jmap_url", into="field.url")
        ctx.click("button.next", measure="manual-url", until=["manual-url-full"])
        ctx.click("button.next", measure="check-login", until=["ready"])


class OutlookClassicSetupFlow(SetupFlow):
    """Outlook (classic), started with an empty profile: its own "Add account" dialog, the default way (no
    "set up manually" option); the pages that follow depend on what Outlook detects for the address."""

    app_kind = "outlook-classic"

    def run(self, ctx: WindowsFlowContext):
        after_connect = ["advanced-setup", "imap-settings", "password", "done", "error"]
        ctx.page(["account-email"], timeout_s=180)
        ctx.type("account.email", into="field.email")
        ctx.click("button.connect", measure="connect", until=after_connect)
        for _ in range(6):
            page = ctx.page(after_connect, timeout_s=30)
            ctx.path(page)
            if page == "error":
                raise ctx.failure("Outlook reports an error in its account setup")
            if page == "advanced-setup":
                ctx.click("tile.imap", measure="choose-imap", until=["imap-settings", "password", "error"])
            elif page == "imap-settings":
                ctx.click("button.next", measure="imap-settings", until=["password", "done", "error"])
            elif page == "password":
                ctx.type("account.password", into="field.password")
                ctx.click("button.connect", measure="login", until=["done", "error", "imap-settings"])
            elif page == "done":
                mobile = ctx.probe.element("checkbox.mobile", timeout_s=2)
                if mobile is not None and mobile.toggle_state == 1:
                    ctx.path("unchecked-outlook-mobile")
                    ctx.click("checkbox.mobile")
                ctx.click("button.done", measure="open-inbox", until=["mail"], final=True)
                return
        raise ctx.failure("Outlook's account setup didn't reach its last page")


class NewOutlookSetupFlow(SetupFlow):
    """New Outlook for Windows: its own "Add account" flow for an IMAP address, which ends with its notice that the
    account is synced through the Microsoft Cloud."""

    app_kind = "outlook-new"

    def run(self, ctx: WindowsFlowContext):
        after_continue = ["choose-provider", "imap-form", "cloud-sync", "success", "mail"]
        page = ctx.page(["add-account", "mail"], timeout_s=180)
        if page == "mail":
            raise ctx.failure("New Outlook already has an account; the test needs it without accounts (the "
                              "previous run's account wasn't removed, or the computer's user has accounts there)")
        ctx.type("account.email", into="field.email")
        ctx.click("button.continue", measure="continue", until=after_continue)
        for _ in range(6):
            page = ctx.page(after_continue, timeout_s=60)
            ctx.path(page)
            if page == "choose-provider":
                ctx.click("option.imap", measure="choose-imap", until=["imap-form", "cloud-sync"])
            elif page == "imap-form":
                ctx.type("account.password", into="field.password")
                ctx.click("button.continue", measure="connect", until=["cloud-sync", "success", "mail"])
            elif page == "cloud-sync":
                ctx.click("button.continue", measure="cloud-sync", until=["success", "mail"])
            elif page == "success":
                ctx.click("button.done", measure="open-inbox", until=["mail"], final=True)
                return
            elif page == "mail":
                if not ctx.final_done:
                    raise ctx.failure("New Outlook shows its mail view, but the last step wasn't measured")
                return
            if ctx.final_done:
                return
        raise ctx.failure("New Outlook's account setup didn't reach its last page")


class NewOutlookRemoval:
    """After a run: Settings → Accounts → Email accounts → Manage (the test account) → Remove → "Remove from all
    devices" (also from the Microsoft Cloud, which Microsoft names as the way to delete the stored credentials).
    Not measured, not user actions; logged with phase "finish"."""

    def __init__(self, email: str):
        self.email = email

    def manage_button(self, ctx: WindowsFlowContext):
        elements = ctx.probe.snapshot()
        account = next((e for e in elements if self.email.lower() in (e.name or "").lower() and e.visible), None)
        buttons = ctx.probe.tree.find_all(ctx.probe.map.query("button.manage"), elements)
        if not buttons:
            raise ctx.failure("No 'Manage' button in new Outlook's account settings")
        if account is None:
            raise ctx.failure(f"New Outlook's account settings don't list {self.email}")
        return min(buttons, key=lambda b: abs(b.center[1] - account.center[1]))

    def run(self, ctx: WindowsFlowContext, wait_gone_s: float = 120):
        ctx.phase = "finish"
        try:
            ctx.click("button.settings")
            ctx.click("nav.accounts")
            if ctx.probe.element("nav.email_accounts", timeout_s=5) is not None:
                ctx.click("nav.email_accounts")
            manage = self.manage_button(ctx)
            ctx.locator.set("button.manage", *manage.center)
            ctx.perform(Action("click", "button.manage"))
            ctx.click("button.remove")
            ctx.click("option.remove_all_devices")
            if ctx.probe.element("button.confirm", timeout_s=5) is not None:
                ctx.click("button.confirm")
            deadline = time.monotonic() + wait_gone_s
            while time.monotonic() < deadline:
                names = " ".join(e.name or "" for e in ctx.probe.snapshot()).lower()
                if self.email.lower() not in names:
                    ctx.log.write("account_removed", email_domain=self.email.split("@")[-1])
                    return True
                time.sleep(2)
            raise ctx.failure(f"{self.email} is still listed in new Outlook {wait_gone_s:.0f} s after its removal")
        finally:
            ctx.phase = "step"


class SetupFlows:
    @staticmethod
    def create(kind: str, **options) -> SetupFlow:
        flows = {"parula": ParulaSetupFlow, "outlook-classic": OutlookClassicSetupFlow,
                 "outlook-new": NewOutlookSetupFlow}
        if kind not in flows:
            raise FlowError(f"No Windows setup flow '{kind}'. Known: {', '.join(flows)}")
        return flows[kind](**options)
