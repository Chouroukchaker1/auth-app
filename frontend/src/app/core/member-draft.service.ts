import { Injectable } from '@angular/core';

export interface PendingFile {
  file: File;
  typeFichier: string;
  /** When the file was picked, as the PC's local date-time (YYYY-MM-DDTHH:mm). */
  addedAt: string;
}

/** The PC's current local date-time, as YYYY-MM-DDTHH:mm (no UTC shift). */
export function localNow(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

/**
 * Unsaved state of the member form, carried across a round trip to the
 * documents page (/member/documents) so nothing typed or picked is lost.
 * Lives in memory only: a page reload drops it.
 */
export interface MemberFormState {
  memberId: number | null;
  /** Query params that reopen the form the way it was opened. */
  returnQuery: Record<string, string>;
  form: unknown;
  members: unknown[];
  marriedSeveralTimes: 'oui' | 'non' | null;
  statut: string;
  pendingFiles: PendingFile[];
}

@Injectable({ providedIn: 'root' })
export class MemberDraftService {
  private state: MemberFormState | null = null;

  keep(state: MemberFormState): void {
    this.state = state;
  }

  /** Current carried state, left in place (used by the documents page). */
  peek(): MemberFormState | null {
    return this.state;
  }

  /** Returns the carried state and clears it (used when the form reopens). */
  take(): MemberFormState | null {
    const state = this.state;
    this.state = null;
    return state;
  }
}
