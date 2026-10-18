// @vitest-environment happy-dom
import { TextBlock } from "../../../../logic/Mail/TextBlock/TextBlock";
import { TextBlocks, textBlocks } from "../../../../logic/Mail/TextBlock/TextBlocks";
import { EMail } from "../../../../logic/Mail/EMail";
import { PersonUID } from "../../../../logic/Abstract/PersonUID";
import TextBlocksHarness from "./TextBlocksHarness.svelte";
import type { Editor } from "@tiptap/core";
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";

// The real one uses DOMPurify, which throws on happy-dom
vi.mock("../../../../logic/util/convertHTML", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../../../logic/util/convertHTML")>(),
  convertHTMLToText: (html: string) => html.replace(/<[^>]*>/g, " ").trim(),
}));

beforeAll(() => {
  (globalThis as any).ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

let app: any;
let target: HTMLElement;
let editor: Editor;

beforeEach(() => {
  localStorage.clear();
  textBlocks.clear();
});

afterEach(() => {
  unmount(app);
  target.remove();
});

async function open(html: string) {
  let mail = new EMail(null);
  mail.to.add(new PersonUID("fred@example.com", "Fred Feuerstein"));
  target = document.createElement("div");
  document.body.append(target);
  app = mount(TextBlocksHarness, { target, props: { mail, html } });
  flushSync();
  await tick();
  editor = app.getEditor();
}

function newTextBlock(keyword: string, html: string): TextBlock {
  let block = new TextBlock();
  block.keyword = keyword;
  block.html = html;
  textBlocks.add(block);
  return block;
}

function button(title: string): HTMLButtonElement {
  return target.querySelector(`button[title="${title}"]`);
}

async function click(element: HTMLElement) {
  element.click();
  flushSync();
  await tick();
  flushSync();
}

async function openTextBlocks() {
  await click(target.querySelector(`button[title^="Text blocks"]`));
}

/** The small editor in the dialog for adding a text block */
function textBlockEditor(): Editor {
  return (target.querySelector(".text-block-edit .tiptap") as any).editor;
}

async function typeKeyword(keyword: string) {
  let input = target.querySelector("#text-block-keyword") as HTMLInputElement;
  input.value = keyword;
  input.dispatchEvent(new Event("input"));
  flushSync();
  await tick();
}

function popup(): HTMLElement {
  return target.querySelector(".text-blocks-popup");
}

test("The selected text is added as text block, with placeholders", async () => {
  await open("<p>Dear Fred,</p><p>Kind greetings, Wilma</p>");
  editor.commands.selectAll();
  await openTextBlocks();
  await click(button("Add the selected text as text block"));
  expect(textBlockEditor().getHTML()).toBe("<p>Dear Fred,</p><p>Kind greetings, Wilma</p>");

  textBlockEditor().commands.setTextSelection({ from: 6, to: 10 });
  await click(button("{name}"));
  textBlockEditor().commands.setTextSelection({ from: 13, to: 13 });
  await click(button("{continue}"));
  expect(textBlockEditor().getHTML()).toBe("<p>Dear {name},{continue}</p><p>Kind greetings, Wilma</p>");
  expect(target.querySelectorAll(".text-block-edit .text-block-placeholder").length).toBe(2);

  await typeKeyword("hi");
  expect(target.querySelector(".text-block-edit .hint").textContent).toContain("Type ::hi in the email");
  await click(button("Add"));

  expect(textBlocks.contents.map(block => block.toJSON())).toEqual([
    { keyword: "hi", html: "<p>Dear {name},{continue}</p><p>Kind greetings, Wilma</p>" },
  ]);
  let saved = new TextBlocks();
  await saved.load();
  expect(saved.first?.keyword).toBe("hi");
  expect(popup()).toBeNull();
});

test("Without selected text, the user writes a new text block", async () => {
  await open("<p>Hello</p>");
  await openTextBlocks();
  await click(button("New text block"));
  expect(textBlockEditor().isEmpty).toBe(true);
  await typeKeyword("::thx");
  expect(button("Please enter the text").disabled).toBe(true);

  textBlockEditor().commands.insertContent("Thank you!");
  flushSync();
  await click(button("Add"));
  expect(textBlocks.first.keyword).toBe("thx");
  expect(textBlocks.first.html).toBe("<p>Thank you!</p>");
});

test("A keyword can exist only once, and has no spaces", async () => {
  newTextBlock("hi", "<p>Hi!</p>");
  await open("<p>Hello</p>");
  editor.commands.selectAll();
  await openTextBlocks();
  await click(button("Add the selected text as text block"));

  await typeKeyword("HI");
  expect(target.querySelector(".text-block-edit .hint.error").textContent).toContain("already a text block with the keyword HI");
  expect(target.querySelector<HTMLButtonElement>(".text-block-edit .buttons button.filled").disabled).toBe(true);

  await typeKeyword("hi there");
  expect(target.querySelector(".text-block-edit .hint.error").textContent).toContain("must not contain spaces");

  await click(button("Cancel"));
  expect(textBlocks.length).toBe(1);
  expect(popup().querySelector(".text-blocks-list")).not.toBeNull();
});

test("Clicking a text block in the list inserts it at the cursor", async () => {
  newTextBlock("hi", "<p>Dear {firstname},</p><p>{continue}</p>");
  await open("<p></p><p>Wilma</p>");
  editor.commands.setTextSelection(1);
  await openTextBlocks();
  await click(target.querySelector(".text-blocks-list button.insert"));

  expect(editor.getHTML()).toBe("<p>Dear Fred,</p><p></p><p>Wilma</p>");
  expect(popup()).toBeNull();
});

test("Editing a text block changes it, and goes back to the list", async () => {
  let block = newTextBlock("hi", "<p>Hi!</p>");
  await open("<p></p>");
  await openTextBlocks();
  await click(button("Edit"));
  expect(textBlockEditor().getHTML()).toBe("<p>Hi!</p>");
  await typeKeyword("hey");
  await click(button("Save"));

  expect(block.keyword).toBe("hey");
  expect(textBlocks.length).toBe(1);
  expect(popup().querySelector(".text-blocks-list").textContent).toContain("::hey");
});

test("Cancel leaves the text block as it was", async () => {
  let block = newTextBlock("hi", "<p>Hi!</p>");
  await open("<p></p>");
  await openTextBlocks();
  await click(button("Edit"));
  await typeKeyword("hey");
  await click(button("Cancel"));
  expect(block.keyword).toBe("hi");
});

test("Deleting a text block asks first", async () => {
  newTextBlock("hi", "<p>Hi!</p>");
  newTextBlock("thx", "<p>Thank you!</p>");
  await open("<p></p>");
  await openTextBlocks();
  let asked: string[] = [];
  window.confirm = (question: string) => {
    asked.push(question);
    return true;
  };
  await click(button("Delete"));

  expect(asked).toEqual(["Do you want to delete the text block ::hi?"]);
  expect(textBlocks.contents.map(block => block.keyword)).toEqual(["thx"]);
});

test("Typing ::keyword shows the matching text blocks, and a click inserts one", async () => {
  newTextBlock("hi", "<p>Hi {name}!</p>");
  newTextBlock("hello", "<p>Hello {name}!</p>");
  newTextBlock("thx", "<p>Thank you!</p>");
  await open("<p></p>");
  editor.commands.insertContent("::h");
  flushSync();

  let suggestions = target.querySelectorAll(".text-block-suggestions button.suggestion");
  expect([...suggestions].map(row => row.textContent)).toEqual([
    expect.stringContaining("::hi"),
    expect.stringContaining("::hello"),
  ]);
  expect(suggestions[0].classList.contains("selected")).toBe(true);

  await click(suggestions[1] as HTMLElement);
  expect(editor.getHTML()).toBe("<p>Hello Fred Feuerstein!</p>");
  expect(target.querySelector(".text-block-suggestions")).toBeNull();
});
