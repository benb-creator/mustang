import type { EMail } from "../EMail";
import { TextBlockPlaceholder } from "./TextBlockPlaceholder";
import { escapeAttr } from "../../Files/FileType/htmlHelper";
import { convertHTMLToText, sanitizeHTMLWithoutStyleTag } from "../../util/convertHTML";
import { sanitize } from "../../../../lib/util/sanitizeDatatypes";
import { Observable, notifyChangedProperty } from "../../util/Observable";

/** Text that the user often writes in emails, e.g. a greeting.
 * Inserted by typing `::keyword`, or from the editor toolbar. */
export class TextBlock extends Observable {
  /** Unique, case-insensitive, without spaces */
  @notifyChangedProperty
  keyword: string;
  /** May contain `TextBlockPlaceholder`s like `{name}` */
  @notifyChangedProperty
  html: string;

  get text(): string {
    return convertHTMLToText(this.html);
  }

  /** @returns `html` with the placeholders filled in with the values from this email.
   * Leaves the placeholders for which the email has no value, and `{continue}`. */
  htmlFor(mail: EMail): string {
    return this.html.replace(TextBlockPlaceholder.kCodeRegExp, (code, key) => {
      let value = TextBlockPlaceholder.byKey(key)?.valueFor(mail);
      return value ? escapeAttr(value) : code;
    });
  }

  matchesKeyword(keyword: string): boolean {
    return this.keyword.toLowerCase() == keyword.toLowerCase();
  }

  fromJSON(json: any) {
    this.keyword = sanitize.nonemptylabel(json.keyword);
    this.html = sanitizeHTMLWithoutStyleTag(sanitize.nonemptystring(json.html));
  }

  toJSON(): any {
    return {
      keyword: this.keyword,
      html: this.html,
    };
  }
}
