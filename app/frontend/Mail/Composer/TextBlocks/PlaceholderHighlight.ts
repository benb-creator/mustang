import { Extension } from "@tiptap/core";
import { Plugin } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import { TextBlockPlaceholder } from "../../../../logic/Mail/TextBlock/TextBlockPlaceholder";

/** Marks the `TextBlockPlaceholder`s like `{name}` with the CSS class `text-block-placeholder` */
export const PlaceholderHighlight = Extension.create({
  name: "placeholderHighlight",

  addProseMirrorPlugins() {
    return [
      new Plugin({
        props: {
          decorations(state) {
            let decorations: Decoration[] = [];
            state.doc.descendants((node, pos) => {
              if (!node.isText) {
                return;
              }
              for (let match of node.text.matchAll(TextBlockPlaceholder.kCodeRegExp)) {
                if (TextBlockPlaceholder.byKey(match[1])) {
                  let from = pos + match.index;
                  decorations.push(Decoration.inline(from, from + match[0].length, { class: "text-block-placeholder" }));
                }
              }
            });
            return DecorationSet.create(state.doc, decorations);
          },
        },
      }),
    ];
  },
});
