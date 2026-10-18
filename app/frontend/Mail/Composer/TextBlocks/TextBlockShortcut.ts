import { Extension, type Range } from "@tiptap/core";
import { Plugin, PluginKey, TextSelection, type EditorState, type Transaction } from "@tiptap/pm/state";
import { DOMParser as ProseMirrorDOMParser } from "@tiptap/pm/model";
import type { EMail } from "../../../../logic/Mail/EMail";
import type { TextBlock } from "../../../../logic/Mail/TextBlock/TextBlock";
import { TextBlockPlaceholder } from "../../../../logic/Mail/TextBlock/TextBlockPlaceholder";
import { textBlocks } from "../../../../logic/Mail/TextBlock/TextBlocks";

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    textBlockShortcut: {
      /** Inserts the text block at `range` (default: the selection),
       * fills in the placeholders, and moves the cursor to `{continue}` */
      insertTextBlock: (block: TextBlock, range?: Range) => ReturnType,
    }
  }
}

export interface TextBlockShortcutOptions {
  /** Where the placeholder values come from */
  getMail: () => EMail;
}

/** Typing `::keyword` offers the matching text blocks.
 * Enter or Tab inserts the selected one, Space the exact match. */
export const TextBlockShortcut = Extension.create<TextBlockShortcutOptions>({
  name: "textBlockShortcut",
  priority: 1000, // before the Enter and Tab keys of the other extensions

  addOptions() {
    return {
      getMail: () => null,
    };
  },

  addCommands() {
    return {
      insertTextBlock: (block, range) => ({ tr, dispatch, editor }) => {
        if (!dispatch) {
          return true;
        }
        let { from, to } = range ?? tr.selection;
        let dom = document.createElement("div");
        dom.innerHTML = block.htmlFor(this.options.getMail());
        let slice = ProseMirrorDOMParser.fromSchema(editor.schema).parseSlice(dom);
        let firstStep = tr.steps.length;
        tr.replaceRange(from, to, slice);
        let mapping = tr.mapping.slice(firstStep);
        let end = mapping.map(to, 1);
        let cursorCode = TextBlockPlaceholder.Cursor.code;
        let cursor: number = null;
        tr.doc.nodesBetween(mapping.map(from, -1), end, (node, pos) => {
          let index = node.isText ? node.text.indexOf(cursorCode) : -1;
          if (cursor == null && index >= 0) {
            cursor = pos + index;
          }
          return cursor == null;
        });
        if (cursor == null) {
          tr.setSelection(TextSelection.near(tr.doc.resolve(end), -1));
        } else {
          tr.delete(cursor, cursor + cursorCode.length);
          tr.setSelection(TextSelection.create(tr.doc, cursor));
        }
        tr.scrollIntoView();
        return true;
      },
    };
  },

  addProseMirrorPlugins() {
    let editor = this.editor;
    return [
      new Plugin<TextBlockSuggestion | null>({
        key: TextBlockSuggestion.key,
        state: {
          init: () => null,
          apply: (tr, previous, oldState, newState) => TextBlockSuggestion.after(tr, previous, newState),
        },
        props: {
          handleKeyDown(view, event) {
            let suggestion = TextBlockSuggestion.of(view.state);
            if (!suggestion?.isOpen ||
                view.composing || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) {
              return false;
            }
            let insert = (block: TextBlock) => editor.chain().focus().insertTextBlock(block, suggestion.range).run();
            switch (event.key) {
              case "ArrowDown":
                view.dispatch(suggestion.select(1, view.state.tr));
                return true;
              case "ArrowUp":
                view.dispatch(suggestion.select(-1, view.state.tr));
                return true;
              case "Enter":
              case "Tab":
                return insert(suggestion.selected);
              case " ":
                return !!suggestion.exactMatch && insert(suggestion.exactMatch);
              case "Escape":
                view.dispatch(view.state.tr.setMeta(TextBlockSuggestion.key, { isDismissed: true }));
                return true;
            }
            return false;
          },
        },
      }),
    ];
  },
});

/** The `::keyword` that the user is typing */
export class TextBlockSuggestion {
  range: Range;
  /** Without the `::` */
  keyword: string;
  matches: TextBlock[];
  selectedIndex = 0;
  /** The user pressed Escape */
  isDismissed = false;

  get isOpen(): boolean {
    return this.matches.length > 0 && !this.isDismissed;
  }

  get selected(): TextBlock {
    return this.matches[this.selectedIndex];
  }

  get exactMatch(): TextBlock | null {
    return this.matches.find(block => block.matchesKeyword(this.keyword)) ?? null;
  }

  /** @param step 1 = next, -1 = previous */
  select(step: number, tr: Transaction): Transaction {
    let selectedIndex = (this.selectedIndex + step + this.matches.length) % this.matches.length;
    return tr.setMeta(TextBlockSuggestion.key, { selectedIndex });
  }

  static readonly key = new PluginKey<TextBlockSuggestion | null>("textBlockSuggestion");

  static of(state: EditorState): TextBlockSuggestion | null {
    return TextBlockSuggestion.key.getState(state) ?? null;
  }

  /** @returns The plugin state after `tr` */
  static after(tr: Transaction, previous: TextBlockSuggestion | null, state: EditorState): TextBlockSuggestion | null {
    let { selection } = state;
    let $cursor = selection.$from;
    if (!selection.empty || !$cursor.parent.isTextblock || $cursor.parent.type.spec.code) {
      return null;
    }
    let textBefore = $cursor.parent.textBetween(0, $cursor.parentOffset, null, "\n");
    let keyword = /(?:^|\s)::(\S*)$/.exec(textBefore)?.[1];
    if (keyword == null) {
      return null;
    }
    let suggestion = new TextBlockSuggestion();
    suggestion.range = { from: $cursor.pos - keyword.length - 2, to: $cursor.pos };
    suggestion.keyword = keyword;
    suggestion.matches = textBlocks.startingWith(keyword);
    let isSameStart = !!previous && tr.mapping.map(previous.range.from) == suggestion.range.from;
    let meta = tr.getMeta(TextBlockSuggestion.key) as Partial<TextBlockSuggestion> | undefined;
    let selectedIndex = meta?.selectedIndex ??
      (isSameStart && previous.keyword == keyword ? previous.selectedIndex : 0);
    suggestion.selectedIndex = Math.min(selectedIndex, Math.max(suggestion.matches.length - 1, 0));
    suggestion.isDismissed = meta?.isDismissed ?? (isSameStart && previous.isDismissed);
    return suggestion;
  }
}
