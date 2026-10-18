import { sanitize } from "../../../lib/util/sanitizeDatatypes";

export function assert(test: boolean | object | string | number | null | undefined, errorMessage: string): asserts test {
  if (!test) {
    throw new Error(errorMessage);
  }
}

/**
 * Waits for a given number of seconds, then continues.
 */
export async function sleep(seconds: number): Promise<void> {
  return new Promise(resolve => {
    setTimeout(resolve, seconds * 1000);
  });
}

export function arrayRemove<T>(array: T[], item: T) {
  let pos = array.indexOf(item);
  if (pos > -1) {
    array.splice(pos, 1);
  }
}

export function arrayRemoveAll<T>(array: T[], item: T) {
  let pos = -1;
  while ((pos = array.indexOf(item, pos)) != -1) {
    array.splice(pos, 1);
  }
}

export function ensureArray<Type>(val: Type[] | Type): Type[] {
  return val ? Array.isArray(val) ? val : [val] : [];
}

export function booleanHasValue(value: boolean | null | undefined): value is boolean {
  return value === true || value === false;
}

export function randomID(): string {
  return Date.now() + "-" + Math.ceil(Math.random() * 900000);
}

export function capitalizeStart(str: string): string {
  return str[0].toLocaleUpperCase() + str.substring(1);
}
export function capitalizeWords(str: string): string {
  return str.split(" ").map(word => capitalizeStart(word)).join(" ");
}

export async function blobToBase64(blob: Blob): Promise<string> {
  let dataURL = await blobToDataURL(blob)
  return dataURL.split(",")[1];
}

export async function blobToDataURL(blob: Blob): Promise<URLString> {
  return new Promise((resolve, reject) => {
    let reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    // The file may be gone or changed on disk, since the user picked it
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/** Decodes base64. */
export function base64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  if (Uint8Array.fromBase64) {
    return Uint8Array.fromBase64(base64);
  }
  // Fallback: node doesn't have it yet, unlike Electron
  // `Uint8Array.from()` with a map is 30x slower = 1.2s for a 20 MB mail
  let binary = atob(base64);
  let bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

export function uint8ArrayToHex(bytes: Uint8Array): string {
  return Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
}

export async function dataURLToBlob(dataURL: URLString): Promise<Blob> {
  let res = await fetch(dataURL);
  return await res.blob();
}

// <copied from="../../frontend/Util/util.ts">
export async function saveBlobAsFile(blob: Blob, filename?: string) {
  const showSaveFilePicker = (window as any).showSaveFilePicker;
  if (typeof(showSaveFilePicker) != "function") { // Fallback
    saveBlobAsFileViaA(blob, filename);
    return;
  }
  if (blob instanceof File) {
    filename = blob.name;
  }
  let handle: any;
  try {
    handle = await showSaveFilePicker({
      suggestedName: filename,
    });
  } catch (ex) {
    if (ex.name == "AbortError") {
      return;
    }
    throw ex;
  }
  let writable = await handle.createWritable();
  await writable.write(blob);
  await writable.close();
}

/** Doesn't work anymore */
export function saveBlobAsFileViaA(blob: Blob, filename?: string) {
  if (blob instanceof File) {
    filename = blob.name;
  }
  let url = URL.createObjectURL(blob);
  saveURLAsFile(url, filename);
  URL.revokeObjectURL(url); // otherwise we leak the entire blob
}

export async function saveBlobAsDataAsFile(blob: Blob, filename?: string) {
  if (blob instanceof File) {
    filename = blob.name;
  }
  let url = await blobToDataURL(blob);
  saveURLAsFile(url, filename);
}

/** Opens a "Save as..." file picker dialog, with the `filename` prefilled,
 * allowing the user to select where to save the file.
 * The content of `url` will be saved in the file.
 *
 * TODO doesn't work anymore
 */
export function saveURLAsFile(url: URLString, filename: string) {
  let a = document.createElement("a");
  a.href = url;
  a.setAttribute("filename", sanitize.filename(filename, "file"));
  a.setAttribute("target", "_blank");
  a.click();
  a.href = '';
}
// </copied>

// <copied from="../../frontend/Util/util.ts">
export function stringFromDataURL(dataURL: URLString, mimetype: string): string | null {
  if (!dataURL || typeof (dataURL) != "string" ||
      dataURL.substring(0, "data:".length + mimetype.length).toLowerCase() != "data:text/html") {
    return null;
  }
  // There might be `;charset=utf-8` in-between
  let comma = dataURL.indexOf(",");
  if (comma < 1) {
    return null;
  }
  let htmlEncoded = dataURL.substring(comma + 1);
  if (!htmlEncoded) {
    return null;
  }
  return decodeURIComponent(htmlEncoded);
}

/** Use as tagged template string:
 * let id = "bar/buu";
 * let name = "Fred Flintstone";
 * URLPart`https://foo/?id=${id}&name=${name}`
 * -> "https://foo/?id=bar%2Fbuu&name=Fred%20Flintstone"
 *
 * Warning: Do *not* escape parts that you want to keep literally in the URL.
 * let baseURL = "https://foo/api"; // ":" and "/" would be escaped
 * let pathname = "com/sub"; // "/" would be escaped
 * URLPart`${baseURL}/${pathname}` // Wrong
 * -> "https%3A%2F%2Ffoo%2Fapi/com%2Fsub"
 */
export function URLPart(literals: TemplateStringsArray, ...values: any[]) {
  return literals.map((literal: string, i: number) => {
    let value = values[i] == undefined ? "" : encodeURIComponent(values[i]);
    return literal + value;
  }).join("");
}
// </copied>

/** TODO Implement this correctly */
export function fileExtensionForMIMEType(mimetype: string) {
  if (typeof (mimetype) == "string" && mimetype != "application/octet-stream") {
    let type = mimetype.split("/")[1];
    if (type) {
      return type;
    }
  }
  return ".ext";
}

/** Abstract class as base class for allowing more specific error classes */
export class SpecificError extends Error {
  constructor(ex: Error, message: string) {
    if (!message) {
      message = ex?.message ?? ex + "";
    }
    super(message);
    if (ex) {
      Object.assign(this, ex);
    }
    this.message = message;
  }
}

/** Replace the error message.
 * Some network exceptions are read-only and setting `ex.message` will throw. */
export function exMessage(ex: Error, message: string): Error {
  try {
    ex.message = message;
    return ex;
  } catch (exDummy) {
    let exNew = new Error(message);
    Object.assign(exNew, ex);
    exNew.name = ex.name;
    exNew.stack = ex.stack;
    exNew.cause = ex;
    exNew.message = message;
    return exNew;
  }
}

/** Used for if/else and switch statements
 * when they run into a case that should not happen */
export class NotReached extends Error {
  constructor(msg?: string) {
    super(msg ?? "Not reached: Unhandled case in code");
  }
}

export class NotImplemented extends Error {
  constructor(msg?: string) {
    super(msg ?? "Not yet implemented");
  }
}

export class NotSupported extends Error {
  constructor(msg?: string) {
    super(msg ?? "Operation not supported");
  }
}

export class UserError extends Error {
  isUserError = true;
}

export class UserCancelled extends UserError {
  doNotShow = true;
  constructor(msg?: string) {
    super(msg ?? "Cancelled");
  }
}

export class AbstractFunction extends Error {
  constructor() {
    super("Not yet implemented");
  }
}

export type URLString = string;
export type Json = { [key: string]: JsonValue } | JsonValue[];
type JsonValue = string | number | boolean | null | Json;
