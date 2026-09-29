import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

export interface MemberSummary {
  id: number;
  nomPrenom: string;
  dateNaissance: string | null;
  numeroUnifie: string;
  numeroAffiliation: string;
  grade: string;
  statut: string;
}

export interface FamilyMemberDto {
  id?: number;
  nom: string;
  prenom: string;
  lienParente: string;
  dateNaissance: string;
}

export interface DocumentDto {
  id: number;
  typeFichier: string;
  filename: string;
  contentType: string;
  size: number;
  /** Upload time; null for documents stored before it was recorded. */
  createdAt: string | null;
}

export interface MemberDetail {
  id: number;
  numeroUnifie: string;
  cnr: string;
  numeroAffiliation: string;
  typeService: string;
  nomPrenom: string;
  grade: string;
  dateNaissance: string;
  lieuNaissance: string;
  debutActivite: string;
  statut: string;
  etatCivil: string;
  dateMariage: string;
  hasPhoto: boolean;
  hasCarteSoins: boolean;
  hasCarteMilitaire: boolean;
  familyMembers: FamilyMemberDto[];
  documents: DocumentDto[];
}

export interface MemberFormPayload {
  numeroUnifie: string;
  cnr: string;
  numeroAffiliation: string;
  typeService: string;
  nomPrenom: string;
  grade: string;
  dateNaissance: string;
  lieuNaissance: string;
  debutActivite: string;
  statut: string;
  etatCivil: string;
  dateMariage: string | null;
  typeFichier: string;
  familyMembers: FamilyMemberDto[];
}

@Injectable({ providedIn: 'root' })
export class MemberService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = '/api/members';

  list(): Observable<MemberSummary[]> {
    return this.http.get<MemberSummary[]>(this.apiUrl);
  }

  getMine(): Observable<MemberDetail> {
    return this.http.get<MemberDetail>(`${this.apiUrl}/me`);
  }

  getById(id: number): Observable<MemberDetail> {
    return this.http.get<MemberDetail>(`${this.apiUrl}/${id}`);
  }

  create(payload: MemberFormPayload, files: { photo?: File | null; carteSoins?: File | null; carteMilitaire?: File | null; documents?: File[] }): Observable<MemberDetail> {
    return this.http.post<MemberDetail>(this.apiUrl, this.buildForm(payload, files));
  }

  update(id: number, payload: MemberFormPayload, files: { photo?: File | null; carteSoins?: File | null; carteMilitaire?: File | null; documents?: File[] }): Observable<MemberDetail> {
    return this.http.put<MemberDetail>(`${this.apiUrl}/${id}`, this.buildForm(payload, files));
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}`);
  }

  deleteDocument(memberId: number, documentId: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${memberId}/documents/${documentId}`);
  }

  getPhotoBlob(id: number): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/${id}/photo`, { responseType: 'blob' });
  }

  getCardBlob(id: number, type: 'soins' | 'militaire'): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/${id}/card/${type}`, { responseType: 'blob' });
  }

  getDocumentBlob(memberId: number, documentId: number): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/${memberId}/documents/${documentId}`, { responseType: 'blob' });
  }

  private buildForm(payload: MemberFormPayload, files: { photo?: File | null; carteSoins?: File | null; carteMilitaire?: File | null; documents?: File[] }): FormData {
    const form = new FormData();
    form.append('data', new Blob([JSON.stringify(payload)], { type: 'application/json' }));
    if (files.photo) form.append('photo', files.photo);
    if (files.carteSoins) form.append('carteSoins', files.carteSoins);
    if (files.carteMilitaire) form.append('carteMilitaire', files.carteMilitaire);
    (files.documents ?? []).forEach(file => form.append('documents', file));
    return form;
  }
}
