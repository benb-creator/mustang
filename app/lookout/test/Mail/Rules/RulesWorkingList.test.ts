// @vitest-environment happy-dom
import { RulesTestAccount } from "./RulesTestAccount";
import { FilterRuleAction } from "../../../../logic/Mail/FilterRules/FilterRuleAction";
import { LocalFilterRule } from "../../../../logic/Mail/FilterRules/LocalFilterRule";
import { ServerFilterRule } from "../../../../logic/Mail/FilterRules/ServerFilterRule";
import { RulesWorkingList } from "../../../Mail/Rules/RulesWorkingList";
import { RuleListActions } from "../../../Mail/Rules/RuleListActions";
import type { MailAccount } from "../../../../logic/Mail/MailAccount";
import { beforeEach, expect, test } from "vitest";

let account: MailAccount;
let saved: number;

function newRule(name: string): FilterRuleAction {
  let rule = new LocalFilterRule(account);
  rule.name = name;
  rule.markAsRead = true;
  account.filterRuleActions.add(rule);
  return rule;
}

beforeEach(() => {
  account = RulesTestAccount.create("a", ["Inbox", "Archive"]);
  saved = 0;
  account.save = async () => { saved++; };
});

test("Changes stay in the working list until Apply", async () => {
  let first = newRule("first");
  newRule("second");
  let list = new RulesWorkingList(account);
  expect(list.isChanged).toBe(false);
  expect(list.rules.contents.map(rule => rule.name)).toEqual(["first", "second"]);
  expect(list.rules.first).not.toBe(first);

  list.rules.first.name = "renamed";
  RuleListActions.move(list.rules, list.rules.first, 1);
  expect(list.isChanged).toBe(true);
  expect(account.filterRuleActions.contents.map(rule => rule.name)).toEqual(["first", "second"]);

  await list.apply();
  expect(saved).toBe(1);
  expect(list.isChanged).toBe(false);
  expect(account.filterRuleActions.contents.map(rule => rule.name)).toEqual(["second", "renamed"]);
  expect(account.filterRuleActions.get(1)).toBe(first);
});

test("Added and removed rules are applied, Apply without changes doesn't save", async () => {
  newRule("first");
  let list = new RulesWorkingList(account);
  await list.apply();
  expect(saved).toBe(0);

  list.rules.removeAll(list.rules.contents);
  let added = new FilterRuleAction(account);
  added.name = "new";
  added.toFolder = RulesTestAccount.folder(account, "Archive");
  list.rules.add(added);
  await list.apply();
  expect(saved).toBe(1);
  expect(account.filterRuleActions.length).toBe(1);
  expect(account.filterRuleActions.first.name).toBe("new");
  expect(account.filterRuleActions.first.toFolder?.name).toBe("Archive");
  expect(account.filterRuleActions.first).not.toBe(added);

  added.name = "changed again";
  await list.apply();
  expect(account.filterRuleActions.length).toBe(1);
  expect(account.filterRuleActions.first.name).toBe("changed again");
});

/** A server rule without parts that we can't show */
class TestServerRule extends ServerFilterRule {
  protected get sections(): Record<string, Record<string, any>> {
    return {};
  }
}

/** @returns The names of the server rules, for each save. "(new)", if the server should create it. */
function letServerRunRules(account: MailAccount): string[][] {
  let uploads: string[][] = [];
  Object.defineProperty(account, "canServerFilterRules", { get: () => true });
  let server = account as any;
  server.newServerFilterRule = () => new TestServerRule(account);
  server.fetchServerFilterRules = async () => account.serverFilterRules
    .filter(rule => rule.serverID)
    .map(rule => rule.clone());
  server.uploadServerFilterRules = async (rules: ServerFilterRule[]) => {
    uploads.push(rules.map(rule => rule.name + (rule.serverID ? "" : " (new)")));
    for (let rule of rules) {
      rule.serverID ??= "id-" + rule.name;
    }
  };
  return uploads;
}

test("A rule that the server created is not created again at the next Apply", async () => {
  let uploads = letServerRunRules(account);
  let list = new RulesWorkingList(account);
  let added = account.newFilterRule(true);
  added.name = "Newsletters";
  list.rules.add(added);
  await list.apply();

  added.markAsRead = true;
  await list.apply();

  expect(uploads).toEqual([["Newsletters (new)"], ["Newsletters"]]);
  expect(account.filterRuleActions.length).toBe(1);
  expect(list.isChanged).toBe(false);
});

test("The user lets the mail server run a rule, and then us again", async () => {
  let uploads = letServerRunRules(account);
  newRule("Newsletters");
  let list = new RulesWorkingList(account);

  let serverRule = RuleListActions.runBy(list.rules, list.rules.first, true);
  expect(list.rules.contents).toEqual([serverRule]);
  expect(list.isChanged).toBe(true);
  await list.apply();
  expect(account.filterRuleActions.first).toBeInstanceOf(ServerFilterRule);
  expect(account.filterRuleActions.first.markAsRead).toBe(true);

  RuleListActions.runBy(list.rules, list.rules.first, false);
  await list.apply();
  expect(account.filterRuleActions.first).toBeInstanceOf(LocalFilterRule);
  expect(account.filterRuleActions.first.markAsRead).toBe(true);
  expect(uploads).toEqual([["Newsletters (new)"], []]);
});

test("A copy of a server rule for another account: That server runs it", () => {
  letServerRunRules(account);
  let secondAccount = RulesTestAccount.create("b", ["Inbox"]);
  letServerRunRules(secondAccount);
  let rule = account.newFilterRule(true) as ServerFilterRule;
  rule.name = "Newsletters";
  rule.markAsRead = true;
  rule.serverID = "rule-1";
  rule.serverJSON = { RuleId: "rule-1" };

  let copy = RuleListActions.copyToAccount(rule, secondAccount, secondAccount.filterRuleActions) as ServerFilterRule;
  expect(copy).toBeInstanceOf(ServerFilterRule);
  expect(copy.markAsRead).toBe(true);
  expect(copy.serverID).toBeNull();
  expect(copy.serverJSON).toEqual({});
});

test("Copy to another account only without folders", () => {
  let secondAccount = RulesTestAccount.create("b", ["Inbox"]);
  let rule = newRule("first");
  expect(RuleListActions.cannotCopyTo(rule, secondAccount)).toBe(false);
  let copy = RuleListActions.copyToAccount(rule, secondAccount, secondAccount.filterRuleActions);
  expect(copy.account).toBe(secondAccount);
  expect(copy.criteria.account).toBe(secondAccount);
  expect(copy.name).toBe("first");
  expect(copy.markAsRead).toBe(true);
  rule.toFolder = RulesTestAccount.folder(account, "Archive");
  expect(RuleListActions.cannotCopyTo(rule, secondAccount)).toBeTruthy();
  expect(RuleListActions.cannotCopyTo(rule, account)).toBe(false);
});
