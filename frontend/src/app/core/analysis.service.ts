import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { AnalysisData, AnalysisJob, OcrResult } from './ocr-import';

/** Document analysis (backend /api/analyses, run by the local document-analysis service). */
@Injectable({ providedIn: 'root' })
export class AnalysisService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = '/api/analyses';

  start(file: File): Observable<AnalysisJob> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<AnalysisJob>(this.apiUrl, form);
  }

  get(id: string): Observable<AnalysisJob> {
    return this.http.get<AnalysisJob>(`${this.apiUrl}/${id}`);
  }

  /** The straightened page the model read. */
  page(id: string): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/${id}/page`, { responseType: 'blob' });
  }

  /** Member-form values from a result corrected by hand. */
  memberForm(data: AnalysisData): Observable<OcrResult> {
    return this.http.post<OcrResult>(`${this.apiUrl}/member-form`, data);
  }
}
