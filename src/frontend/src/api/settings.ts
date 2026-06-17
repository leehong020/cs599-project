export interface WorkingHours {
  start: string;
  end: string;
}

export interface UserProfile {
  user_id: string;
  email: string;
  display_name: string | null;
  timezone: string | null;
  default_calendar_id: string | null;
  default_signature_id: string | null;
  default_sender_email: string | null;
  default_meeting_duration_minutes: number | null;
  meeting_buffer_minutes: number;
  working_hours: WorkingHours | null;
  lunch_break: WorkingHours | null;
  email_tone_internal: string | null;
  email_tone_external: string | null;
}

export interface Signature {
  id: string;
  label: string;
  content: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface Contact {
  id: string;
  display_name: string;
  email: string;
  created_at: string;
  updated_at: string;
}

export interface ProfileForm {
  timezone: string | null;
  default_calendar_id: string | null;
  default_signature_id: string | null;
  default_sender_email: string | null;
  default_meeting_duration_minutes: number | null;
  meeting_buffer_minutes: number;
  working_hours: WorkingHours | null;
  lunch_break: WorkingHours | null;
  email_tone_internal: string | null;
  email_tone_external: string | null;
}

export interface SignatureCreateForm {
  label?: string;
  content: string;
  is_default?: boolean;
}

export interface SignatureUpdateForm {
  label?: string;
  content?: string;
  is_default?: boolean;
}

export interface ContactForm {
  display_name: string;
  email: string;
}

// settings/profile 是后续字段完整性校验的事实来源。这里保留类型化
// 请求，避免前端把空字符串和真正的 null 混在一起。
export async function fetchProfile(): Promise<UserProfile> {
  const response = await fetch("/api/settings/profile");

  if (!response.ok) {
    throw new Error(`Profile fetch failed with ${response.status}`);
  }

  return response.json() as Promise<UserProfile>;
}

export async function saveProfile(payload: ProfileForm): Promise<UserProfile> {
  const response = await fetch("/api/settings/profile", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Profile save failed with ${response.status}`);
  }

  return response.json() as Promise<UserProfile>;
}

export async function fetchSignatures(): Promise<Signature[]> {
  const response = await fetch("/api/settings/signatures");

  if (!response.ok) {
    throw new Error(`Signatures fetch failed with ${response.status}`);
  }

  return response.json() as Promise<Signature[]>;
}

export async function createSignature(payload: SignatureCreateForm): Promise<Signature> {
  const response = await fetch("/api/settings/signatures", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Signature create failed with ${response.status}`);
  }

  return response.json() as Promise<Signature>;
}

export async function updateSignature(
  signatureId: string,
  payload: SignatureUpdateForm,
): Promise<Signature> {
  const response = await fetch(`/api/settings/signatures/${encodeURIComponent(signatureId)}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Signature update failed with ${response.status}`);
  }

  return response.json() as Promise<Signature>;
}

export async function fetchContacts(): Promise<Contact[]> {
  const response = await fetch("/api/settings/contacts");

  if (!response.ok) {
    throw new Error(`Contacts fetch failed with ${response.status}`);
  }

  return response.json() as Promise<Contact[]>;
}

export async function createContact(payload: ContactForm): Promise<Contact> {
  const response = await fetch("/api/settings/contacts", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Contact create failed with ${response.status}`);
  }

  return response.json() as Promise<Contact>;
}

export async function updateContact(contactId: string, payload: ContactForm): Promise<Contact> {
  const response = await fetch(`/api/settings/contacts/${encodeURIComponent(contactId)}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Contact update failed with ${response.status}`);
  }

  return response.json() as Promise<Contact>;
}

export async function deleteContact(contactId: string): Promise<void> {
  const response = await fetch(`/api/settings/contacts/${encodeURIComponent(contactId)}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(`Contact delete failed with ${response.status}`);
  }
}
