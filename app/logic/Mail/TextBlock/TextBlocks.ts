import { TextBlock } from "./TextBlock";
import { logError } from "../../../frontend/Util/error";
import { sanitize } from "../../../../lib/util/sanitizeDatatypes";
import { ArrayColl } from "svelte-collections";

export class TextBlocks extends ArrayColl<TextBlock> {
  protected static readonly kStorageKey = "mail.textBlocks";

  async load() {
    let json: any[] = sanitize.array(JSON.parse(sanitize.nonemptystring(localStorage.getItem(TextBlocks.kStorageKey), "[]")), []);
    let blocks: TextBlock[] = [];
    for (let blockJSON of json) {
      try {
        let block = new TextBlock();
        block.fromJSON(blockJSON);
        blocks.push(block);
      } catch (ex) {
        logError(ex);
      }
    }
    this.replaceAll(blocks);
  }

  async save() {
    let json = this.contents.map(block => block.toJSON());
    localStorage.setItem(TextBlocks.kStorageKey, JSON.stringify(json));
  }

  getByKeyword(keyword: string): TextBlock | null {
    return this.find(block => block.matchesKeyword(keyword)) ?? null;
  }

  /** @returns the shortest keyword first, so an exact match comes first */
  startingWith(prefix: string): TextBlock[] {
    prefix = prefix.toLowerCase();
    return this.contents
      .filter(block => block.keyword.toLowerCase().startsWith(prefix))
      .sort((a, b) => a.keyword.length - b.keyword.length || a.keyword.localeCompare(b.keyword));
  }
}

export const textBlocks = new TextBlocks();
