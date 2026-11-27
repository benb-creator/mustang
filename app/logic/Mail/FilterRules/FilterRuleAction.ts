import { FilterMoment } from "./FilterMoments";
import { SearchEMail } from "../Store/SearchEMail";
import type { MailAccount } from "../MailAccount";
import type { Folder } from "../Folder";
import { getTagByName, type Tag } from "../../Abstract/Tag";
import { notifyChangedProperty, Observable } from "../../util/Observable";
import { sanitize } from "../../../../lib/util/sanitizeDatatypes";
import { SetColl } from "svelte-collections";

/** Does automatic user-defined actions on emails,
 * on defined moments (e.g. new email arrived, email sent etc.),
 * for emails that match user-defined criteria.
 * We run a `LocalFilterRule`, the mail server a `ServerFilterRule`. */
export class FilterRuleAction extends Observable {
  @notifyChangedProperty
  name: string = "";
  /** For which email and at which moment the filter should be run */
  @notifyChangedProperty
  when: FilterMoment = FilterMoment.IncomingBeforeSpam;
  /** For which subset of emails the filter should run */
  readonly criteria = new SearchEMail();

  /** Why the user cannot change this rule. null, if they can. */
  get readOnlyReason(): string | null {
    return null;
  }

  /** The following actions cannot be combined:
   * - Delete/spam actions with toFolder or markAsStarred
   */
  /** Move or copy (`copyToFolder`) the email to this folder. */
  _toFolder: Folder | null = null;
  @notifyChangedProperty
  toFolderID: string | undefined;
  get toFolder(): Folder | null {
    return (this.toFolderID && (this._toFolder ??= this.account.findFolder(folder => folder.id == this.toFolderID))) ?? null;
  }
  set toFolder(folder: Folder | null) {
    this._toFolder = folder;
    this.toFolderID = folder?.id;
  }
  /** If `toFolder` and `copyToFolder`, then copy the email. instead of moving. */
  @notifyChangedProperty
  copy: boolean | null = null;
  readonly account: MailAccount;
  readonly addTags = new SetColl<Tag>();

  @notifyChangedProperty
  markAsRead: boolean | null = null;
  @notifyChangedProperty
  markAsStarred: boolean | null = null;

  /** Marks the message as spam, and maybe moves it to the spam folder */
  @notifyChangedProperty
  markAsSpam: boolean | null = null;
  /** Move the message to the trash folder */
  @notifyChangedProperty
  deleteTrash: boolean | null = null;
  /** Make this message disappear immediately. Do not move to trash. Use with care. */
  @notifyChangedProperty
  deleteImmediately: boolean | null = null;

  constructor(account: MailAccount, criteria?: SearchEMail) {
    super();
    if (criteria) {
      this.criteria = criteria;
    }
    this.criteria.account = this.account = account;
  }

  /** The same rule, run by the mail server, if `server`, otherwise by us.
   * Throws, if that one cannot run all parts of the rule.
   * @returns This rule, or one of the other class, which replaces this one in the lists */
  runBy(server: boolean): FilterRuleAction {
    let rule = this.account.newFilterRule(server);
    rule.fromJSON(this.toJSON());
    rule.name = this.name;
    return rule;
  }

  fromJSON(json: any) {
    this.name = sanitize.nonemptystring(json.name, "-");
    this.when = sanitize.enum<FilterMoment>(json.when, Object.values(FilterMoment));
    this.criteria.fromJSON(json.criteria);
    this.criteria.account = this.account;
    function boolean(value: boolean | undefined): boolean | undefined {
      return typeof (value) == "boolean" ? value : undefined;
    }
    this.markAsRead = boolean(json.markAsRead);
    this.markAsStarred = boolean(json.markAsStarred);
    this.markAsSpam = boolean(json.markAsSpam);
    this.deleteTrash = boolean(json.deleteTrash);
    this.deleteImmediately = boolean(json.deleteImmediately);
    this.copy = boolean(json.copy);
    // let folderAccount = appGlobal.emailAccounts.find(acc => acc.id == json.toFolderAccountID);
    this.toFolderID = sanitize.nonemptystring(json.toFolder, null);
    this._toFolder = null;
    this.addTags.replaceAll(sanitize.array(json.addTags, [])?.map(name => getTagByName(name)));
  }

  toJSON() {
    return {
      name: this.name,
      when: this.when,
      criteria: this.criteria.toJSON(),
      markAsRead: this.markAsRead,
      markAsStarred: this.markAsStarred,
      markAsSpam: this.markAsSpam,
      deleteTrash: this.deleteTrash,
      deleteImmediately: this.deleteImmediately,
      copy: this.copy,
      // toFolderAccountID: this.toFolder?.account?.id,
      toFolder: this.toFolderID,
      addTags: this.addTags.contents.map(tag => tag.name),
    };
  }

  clone(): FilterRuleAction {
    let clone = new (this as any).constructor(this.account);
    clone.fromJSON(this.toJSON());
    return clone;
  }
}
