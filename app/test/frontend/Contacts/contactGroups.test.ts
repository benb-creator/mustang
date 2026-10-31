// @vitest-environment happy-dom
// app first, to resolve the import cycle around Abstract/Account.ts
import { appGlobal } from "../../../logic/app";
import { ContactEntry } from "../../../logic/Abstract/Person";
import { Addressbook } from "../../../logic/Contacts/Addressbook";
import ContactBoxes from "../../../frontend/Contacts/PersonPage/ContactBoxes.svelte";
import { flushSync, mount, unmount } from "svelte";
import { afterEach, beforeAll, expect, test } from "vitest";

let target: HTMLElement;
let app: ReturnType<typeof mount>;

beforeAll(() => {
  appGlobal.remoteApp = {} as any;
});

afterEach(() => {
  unmount(app);
  target.remove();
});

function showGroups(isEditing: boolean): string {
  let person = new Addressbook().newPerson();
  person.name = "Anna";
  person.groups.add(new ContactEntry("Sales team", "Mustang"));
  person.groups.add(new ContactEntry("Hiking club", "WhatsApp"));
  target = document.createElement("div");
  document.body.append(target);
  app = mount(ContactBoxes, { target, props: { person, isEditing, showExpanders: false } });
  flushSync();
  return target.querySelector(".groups").textContent;
}

test("The contact shows the names of its groups", () => {
  let groups = showGroups(false);
  expect(groups).toContain("Sales team");
  expect(groups).toContain("Hiking club");
});

test("While editing the contact, it still shows the names of its groups", () => {
  let groups = showGroups(true);
  expect(groups).toContain("Sales team");
  expect(groups).toContain("Hiking club");
});
