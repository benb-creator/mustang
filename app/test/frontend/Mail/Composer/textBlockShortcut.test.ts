// @vitest-environment happy-dom
import { TextBlockShortcut, TextBlockSuggestion } from "../../../../frontend/Mail/Composer/TextBlocks/TextBlockShortcut";
import { ParagraphNewLine } from "../../../../frontend/Shared/Editor/ParagraphNewLine";
import { TextBlock } from "../../../../logic/Mail/TextBlock/TextBlock";
import { TextBlocks, textBlocks } from "../../../../logic/Mail/TextBlock/TextBlocks";
import { EMail } from "../../../../logic/Mail/EMail";
import { PersonUID } from "../../../../logic/Abstract/PersonUID";
import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { beforeEach, expect, test } from "vitest";

let mail: EMail;

beforeEach(() => {
  mail = new EMail(null);
  mail.to.add(new PersonUID("fred@example.com", "Fred Feuerstein"));
  textBlocks.clear();
  textBlocks.add(newTextBlock("hi", "<p>Dear {firstname},</p><p>{continue}</p><p>Kind greetings,<br>Wilma</p>"));
  textBlocks.add(newTextBlock("hello", "<p>Hello {name}!</p>"));
  textBlocks.add(newTextBlock("thx", "<p>Thank you!</p>"));
});

function newTextBlock(keyword: string, html: string): TextBlock {
  let block = new TextBlock();
  block.keyword = keyword;
  block.html = html;
  return block;
}

function newEditor(content = "<p></p>"): Editor {
  let element = document.createElement("div");
  document.body.append(element);
  // Same order as in `HTMLEditor`: the extra extensions come last
  return new Editor({
    element,
    extensions: [
      StarterKit,
      ParagraphNewLine,
      TextBlockShortcut.configure({ getMail: () => mail }),
    ],
    content,
  });
}

/** Lets ProseMirror handle the key, like a real key press does */
function pressKey(editor: Editor, key: string): boolean {
  let event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
  editor.view.dom.dispatchEvent(event);
  return event.defaultPrevented;
}

function type(editor: Editor, text: string) {
  editor.commands.insertContent(text);
}

test("Placeholders are filled in from the email, unknown ones stay", () => {
  let block = newTextBlock("x", "<p>{name} <{email}> {firstname} {lastname} {unknown} {continue}</p>");
  expect(block.htmlFor(mail)).toBe("<p>Fred Feuerstein <fred@example.com> Fred Feuerstein {unknown} {continue}</p>");
});

test("Placeholder values are HTML-escaped", () => {
  mail.to.first.name = `<b>Fred</b> "the rock"`;
  let block = newTextBlock("x", "<p>Dear {name}</p>");
  expect(block.htmlFor(mail)).toBe("<p>Dear &lt;b&gt;Fred&lt;/b&gt; &quot;the rock&quot;</p>");
});

test("Placeholders without value in this email stay, so that the user notices them", () => {
  mail.to.clear();
  let block = newTextBlock("x", "<p>Dear {name},</p>");
  expect(block.htmlFor(mail)).toBe("<p>Dear {name},</p>");
});

test("::keyword and Enter inserts the text block, and the cursor goes to {continue}", () => {
  let editor = newEditor();
  type(editor, "::hi");
  expect(TextBlockSuggestion.of(editor.state)?.isOpen).toBe(true);

  expect(pressKey(editor, "Enter")).toBe(true);
  expect(editor.getHTML()).toBe("<p>Dear Fred,</p><p></p><p>Kind greetings,<br>Wilma</p>");

  type(editor, "Thanks for the rock");
  expect(editor.getHTML()).toBe("<p>Dear Fred,</p><p>Thanks for the rock</p><p>Kind greetings,<br>Wilma</p>");
  expect(TextBlockSuggestion.of(editor.state)).toBeNull();
});

test("Space after the exact keyword inserts it", () => {
  let editor = newEditor("<p>Yes.</p>");
  editor.commands.focus("end");
  type(editor, " ::thx");

  expect(pressKey(editor, " ")).toBe(true);
  expect(editor.getHTML()).toBe("<p>Yes. Thank you!</p>");
});

test("Space after a partial keyword is a normal space", () => {
  let editor = newEditor();
  type(editor, "::th");

  expect(pressKey(editor, " ")).toBe(false);
});

test("The shortest keyword comes first, arrow keys select the others", () => {
  let editor = newEditor();
  type(editor, "::h");
  let suggestion = TextBlockSuggestion.of(editor.state);
  expect(suggestion.matches.map(block => block.keyword)).toEqual(["hi", "hello"]);
  expect(suggestion.selected.keyword).toBe("hi");

  pressKey(editor, "ArrowDown");
  expect(TextBlockSuggestion.of(editor.state).selected.keyword).toBe("hello");
  pressKey(editor, "ArrowDown");
  expect(TextBlockSuggestion.of(editor.state).selected.keyword).toBe("hi");
  pressKey(editor, "ArrowUp");
  expect(TextBlockSuggestion.of(editor.state).selected.keyword).toBe("hello");

  pressKey(editor, "Tab");
  expect(editor.getHTML()).toBe("<p>Hello Fred Feuerstein!</p>");
});

test("Typing more of the keyword narrows the list", () => {
  let editor = newEditor();
  type(editor, "::he");
  expect(TextBlockSuggestion.of(editor.state).matches.map(block => block.keyword)).toEqual(["hello"]);
  type(editor, "x");
  expect(TextBlockSuggestion.of(editor.state).isOpen).toBe(false);
  expect(pressKey(editor, "Enter")).toBe(true); // ParagraphNewLine
  expect(editor.getHTML()).toBe("<p>::hex<br></p>");
});

test("Escape closes the list, and Enter is a normal Enter again", () => {
  let editor = newEditor();
  type(editor, "::hi");
  expect(pressKey(editor, "Escape")).toBe(true);
  expect(TextBlockSuggestion.of(editor.state).isOpen).toBe(false);

  pressKey(editor, "Enter");
  expect(editor.getHTML()).toBe("<p>::hi<br></p>");
});

test("Escape keeps the list closed while typing on", () => {
  let editor = newEditor();
  type(editor, "::h");
  pressKey(editor, "Escape");
  type(editor, "i");
  expect(TextBlockSuggestion.of(editor.state).isOpen).toBe(false);
  pressKey(editor, "Enter");
  expect(editor.getHTML()).toBe("<p>::hi<br></p>");
});

test("Keywords are case-insensitive", () => {
  let editor = newEditor();
  type(editor, "::THX");
  pressKey(editor, " ");
  expect(editor.getHTML()).toBe("<p>Thank you!</p>");
});

test(":: within a word is not a shortcut", () => {
  let editor = newEditor();
  type(editor, "std::hi");
  expect(TextBlockSuggestion.of(editor.state)).toBeNull();
});

test(":: after a line break is a shortcut", () => {
  let editor = newEditor("<p>Hi<br>::thx</p>");
  editor.commands.focus("end");
  expect(TextBlockSuggestion.of(editor.state)?.isOpen).toBe(true);
});

test("Inserting from the toolbar replaces the selection", () => {
  let editor = newEditor("<p>Yes. Thanks</p>");
  editor.commands.setTextSelection({ from: 6, to: 12 });
  editor.commands.insertTextBlock(textBlocks.getByKeyword("thx"));
  expect(editor.getHTML()).toBe("<p>Yes. Thank you!</p>");
});

test("Text blocks are saved and loaded", async () => {
  await textBlocks.save();
  let loaded = new TextBlocks();
  await loaded.load();
  expect(loaded.contents.map(block => block.keyword)).toEqual(["hi", "hello", "thx"]);
  // happy-dom's DOMPurify drops the first `<p>` tag, Chromium's doesn't
  expect(loaded.getByKeyword("hi").html).toContain("{firstname},<p>{continue}</p><p>Kind greetings,<br>Wilma</p>");
});

// DOMPurify doesn't work in happy-dom, so this can't test that loading sanitizes the HTML
test("Loading skips broken text blocks", async () => {
  localStorage.setItem("mail.textBlocks", JSON.stringify([
    { keyword: "x", html: "<p>Hi</p>" },
    { keyword: "", html: "<p>No keyword</p>" },
    { keyword: "nohtml" },
  ]));
  let loaded = new TextBlocks();
  await loaded.load();
  expect(loaded.contents.map(block => block.keyword)).toEqual(["x"]);
});
