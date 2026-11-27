import { FilterRuleAction } from "../../../logic/Mail/FilterRules/FilterRuleAction";
import { LocalFilterRule } from "../../../logic/Mail/FilterRules/LocalFilterRule";
import { ServerFilterRule } from "../../../logic/Mail/FilterRules/ServerFilterRule";
import type { Folder } from "../../../logic/Mail/Folder";
import type { MailAccount } from "../../../logic/Mail/MailAccount";
import { appName } from "../../../logic/build";
import { gt } from "../../../l10n/l10n";
import type { ArrayColl } from "svelte-collections";

export class RuleListActions {
  static move(rules: ArrayColl<FilterRuleAction>, rule: FilterRuleAction, offset: number) {
    let index = rules.indexOf(rule);
    let newIndex = index + offset;
    if (index < 0 || newIndex < 0 || newIndex >= rules.length) {
      return;
    }
    rules.splice(index, 1);
    rules.splice(newIndex, 0, rule);
  }

  static copy(rules: ArrayColl<FilterRuleAction>, rule: FilterRuleAction): FilterRuleAction {
    let copy = rule.clone();
    copy.name = gt`Copy of ${rule.name}`;
    if (copy instanceof ServerFilterRule) {
      copy.serverID = null;
    }
    let index = rules.indexOf(rule);
    if (index < 0) {
      rules.add(copy);
    } else {
      rules.splice(index + 1, 0, copy);
    }
    return copy;
  }

  static cannotCopyTo(rule: FilterRuleAction, account: MailAccount): string | false {
    if (account == rule.account) {
      return false;
    }
    if (rule.toFolderID || rule.criteria.folderID) {
      return gt`This rule uses a folder of ${rule.account.name}, so it can only be copied within that account`;
    }
    if (rule instanceof ServerFilterRule && rule.unknownParts.length) {
      return gt`This rule has parts that ${appName} cannot show, so it can only be copied within ${rule.account.name}`;
    }
    return false;
  }

  static copyToAccount(rule: FilterRuleAction, account: MailAccount, rules: ArrayColl<FilterRuleAction>): FilterRuleAction {
    if (account == rule.account) {
      return RuleListActions.copy(rules, rule);
    }
    let local = new LocalFilterRule(account);
    local.fromJSON(rule.toJSON());
    local.name = rule.name;
    // Without the parts that only the server of `rule` knows
    let copy = rule instanceof ServerFilterRule && account.canServerFilterRules ? local.runBy(true) : local;
    rules.add(copy);
    return copy;
  }

  /** Lets the mail server or us run the rule. The rule of the other class replaces it in `rules`. */
  static runBy(rules: ArrayColl<FilterRuleAction>, rule: FilterRuleAction, server: boolean): FilterRuleAction {
    let changed = rule.runBy(server);
    rules.splice(rules.indexOf(rule), 1, changed);
    return changed;
  }

  static moveToFolder(rule: FilterRuleAction, folder: Folder, copy: boolean) {
    rule.toFolder = folder;
    rule.copy = copy;
    rule.deleteTrash = null;
    rule.deleteImmediately = null;
    if (rule.markAsSpam) {
      rule.markAsSpam = null;
    }
  }

  static deleteMessage(rule: FilterRuleAction) {
    // <copied from="../../../frontend/Mail/Search/RuleActions.svelte" updateDelete()>
    rule.markAsSpam = rule.markAsSpam ? true : null;
    rule.markAsStarred = null;
    rule.copy = null;
    rule.toFolder = null;
    rule.addTags.clear();
    // </copied>
    rule.deleteTrash = true;
    rule.deleteImmediately = null;
  }
}
