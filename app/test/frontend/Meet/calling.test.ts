// @vitest-environment happy-dom
// app first, to resolve the import cycle around Abstract/Account.ts
import { appGlobal } from "../../../logic/app";
import { ContactEntry } from "../../../logic/Abstract/Person";
import { Addressbook } from "../../../logic/Contacts/Addressbook";
import { MeetingState, VideoConfMeeting } from "../../../logic/Meet/VideoConfMeeting";
import { MeetingParticipant } from "../../../logic/Meet/Participant";
import { Observable } from "../../../logic/util/Observable";
import Calling from "../../../frontend/Meet/Start/Calling.svelte";
import { flushSync, mount, unmount } from "svelte";
import { afterEach, beforeAll, expect, test } from "vitest";

let target: HTMLElement;
let app: ReturnType<typeof mount>;

beforeAll(() => {
  (globalThis as any).ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  appGlobal.remoteApp = {} as any;
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: {
    enumerateDevices: async () => [],
    addEventListener() {},
    removeEventListener() {},
  } });
  let addressbook = new Addressbook();
  appGlobal.addressbooks.add(addressbook);
  let anna = addressbook.newPerson();
  anna.name = "Anna";
  anna.emailAddresses.add(new ContactEntry("anna@example.com", "work"));
  addressbook.persons.add(anna);
});

afterEach(() => {
  unmount(app);
  target.remove();
});

function showCall(emailAddress: string, hasVideo: boolean) {
  let meeting = new VideoConfMeeting();
  meeting.account = { canVideo: true, canAudio: true, canScreenShare: false, protocol: "test" } as any;
  meeting.mediaDeviceStreams = new Observable() as any;
  meeting.hasVideo = hasVideo;
  meeting.state = MeetingState.OutgoingCallConfirm;
  let callee = new MeetingParticipant();
  callee.name = "Anna";
  callee.emailAddress = emailAddress;
  meeting.participants.add(callee);
  target = document.createElement("div");
  document.body.append(target);
  app = mount(Calling, { target, props: { meeting } });
  flushSync();
  return {
    call: target.querySelector(".what")?.textContent.trim(),
    contactHistory: !!target.querySelector(".contact-history"),
  };
}

test("A video call to a known contact shows the call, without contact history", () => {
  expect(showCall("anna@example.com", true)).toEqual({ call: "Do you want to call?", contactHistory: false });
});

test("A phone call to a known contact shows the call and the contact history", () => {
  expect(showCall("anna@example.com", false)).toEqual({ call: "Do you want to call?", contactHistory: true });
});

test("A call to an unknown person shows the call, without an empty contact history", () => {
  expect(showCall("bob@example.com", false)).toEqual({ call: "Do you want to call?", contactHistory: false });
});
