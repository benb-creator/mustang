import type { EMail } from "../EMail";
import { FilterRuleAction } from "./FilterRuleAction";
import { DeleteStrategy } from "../MailAccount";
import { assert, booleanHasValue } from "../../util/util";
import { gt } from "../../../l10n/l10n";

/** A filter rule that we run, on the emails that we download */
export class LocalFilterRule extends FilterRuleAction {
  /** Checks for a match, and runs the filter action, as needed. */
  async run(email: EMail): Promise<void> {
    if (!this.criteria.matches(email)) {
      return;
    }
    await this.doAction(email);
  }

  /** Executes the filter action.
   * Unconditionally, i.e. does not check for match. */
  async doAction(email: EMail): Promise<void> {
    if (booleanHasValue(this.markAsRead)) {
      await email.markRead(this.markAsRead);
    }
    if (booleanHasValue(this.markAsStarred)) {
      await email.markStarred(this.markAsStarred);
    }
    if (this.addTags.hasItems) {
      for (let tag of this.addTags) {
        await email.addTag(tag);
      }
    }
    if (booleanHasValue(this.markAsSpam)) {
      await email.treatSpam(this.markAsSpam);
      if (this.markAsSpam) {
        return;
      }
    }
    if (this.deleteImmediately) {
      await email.deleteMessage(DeleteStrategy.DeleteImmediately);
      return;
    }
    if (this.deleteTrash) {
      await email.deleteMessage(DeleteStrategy.MoveToTrash);
      return;
    }
    if (this.toFolderID) {
      assert(this.toFolder, gt`The target folder of filter rule ${this.name} does not exist anymore`);
      if (this.copy) {
        await this.toFolder.copyMessageHere(email);
      } else {
        await this.toFolder.moveMessageHere(email);
      }
    }
  }

  runBy(server: boolean): FilterRuleAction {
    return server ? super.runBy(server) : this;
  }
}
