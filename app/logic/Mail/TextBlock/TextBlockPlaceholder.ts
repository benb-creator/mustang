import type { EMail } from "../EMail";
import type { PersonUID } from "../../Abstract/PersonUID";
import { getDateTimeLocale, gt } from "../../../l10n/l10n";

/** A variable like `{name}` in a `TextBlock`,
 * which is replaced with a value from the email when inserting the text block. */
export class TextBlockPlaceholder {
  readonly key: string;
  protected readonly getLabel: () => string;
  protected readonly getValue: (mail: EMail) => string | null | undefined;

  constructor(key: string, getLabel: () => string, getValue: (mail: EMail) => string | null | undefined) {
    this.key = key;
    this.getLabel = getLabel;
    this.getValue = getValue;
  }

  /** As it appears in the text block, e.g. `{name}` */
  get code(): string {
    return `{${this.key}}`;
  }

  get label(): string {
    return this.getLabel();
  }

  /** @returns null, if this email doesn't have a value for it,
   * e.g. because it has no recipient yet */
  valueFor(mail: EMail): string | null {
    return this.getValue(mail) || null;
  }

  /** Matches a placeholder code. Group 1 is the key. */
  static readonly kCodeRegExp = /\{(\w+)\}/g;

  static byKey(key: string): TextBlockPlaceholder | null {
    return TextBlockPlaceholder.all.find(placeholder => placeholder.key == key) ?? null;
  }

  /** Where the cursor goes after inserting the text block */
  static readonly Cursor = new TextBlockPlaceholder("continue", () => gt`Cursor`, () => null);

  static readonly all: TextBlockPlaceholder[] = [
    new TextBlockPlaceholder("name", () => gt`Name`, mail => mail.to.first?.name),
    new TextBlockPlaceholder("firstname", () => gt`First name`, mail => TextBlockPlaceholder.nameParts(mail.to.first)?.firstName),
    new TextBlockPlaceholder("lastname", () => gt`Last name`, mail => TextBlockPlaceholder.nameParts(mail.to.first)?.lastName),
    new TextBlockPlaceholder("email", () => gt`Email address`, mail => mail.to.first?.emailAddress),
    new TextBlockPlaceholder("myname", () => gt`My name`, mail => mail.from?.name || mail.identity?.realname),
    new TextBlockPlaceholder("date", () => gt`Date`, () => new Date().toLocaleDateString(getDateTimeLocale(), { year: "numeric", month: "long", day: "numeric" })),
    new TextBlockPlaceholder("time", () => gt`Time`, () => new Date().toLocaleTimeString(getDateTimeLocale(), { hour: "numeric", minute: "numeric" })),
    TextBlockPlaceholder.Cursor,
  ];

  protected static nameParts(recipient: PersonUID | undefined): { firstName: string, lastName: string } | null {
    if (!recipient?.name) {
      return null;
    }
    let person = recipient.findPerson();
    if (person?.firstName && person?.lastName) {
      return { firstName: person.firstName, lastName: person.lastName };
    }
    let words = recipient.name.trim().split(/\s+/);
    let lastName = words.length > 1 ? words.pop() : null;
    return { firstName: words.join(" "), lastName };
  }
}
