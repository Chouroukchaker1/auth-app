import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AnalysisService } from '../../core/analysis.service';
import { AuthService } from '../../core/auth.service';
import { httpErrorMessage } from '../../core/http-errors';
import { MemberDraftService } from '../../core/member-draft.service';
import { AnalysisData, AnalysisJob, CONF_GOOD, CONF_MEDIUM } from '../../core/ocr-import';
import { SiteFooterComponent } from '../layout/site-footer.component';
import { TopbarComponent } from '../layout/topbar.component';

const MAX_BYTES = 10 * 1024 * 1024;
const POLL_MS = 1500;
const EDITED = 'corrigé à la main';
/** Running analysis, so coming back to this page (or reloading it) picks it up again. */
const JOB_KEY = 'analysis_job';

/**
 * Reads a paper form (photo, scan or PDF) and fills the member form with the values found
 * ("تحليل وثيقة" on the member form). Every value can be corrected before it is sent.
 */
@Component({
  selector: 'app-document-analysis',
  imports: [TopbarComponent, SiteFooterComponent],
  templateUrl: './document-analysis.component.html',
  styleUrl: './document-analysis.component.scss'
})
export class DocumentAnalysisComponent implements OnInit, OnDestroy {
  private readonly authService = inject(AuthService);
  private readonly analysis = inject(AnalysisService);
  private readonly drafts = inject(MemberDraftService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  protected session = { fullName: '', subtitle: '' };
  protected file: File | null = null;
  protected previewUrl: string | null = null;
  protected dragging = false;
  protected job: AnalysisJob | null = null;
  protected data: AnalysisData | null = null;
  protected pageUrl: string | null = null;
  protected sending = false;
  protected errorMessage: string | null = null;
  protected elapsed = 0;

  private returnQuery: Record<string, string> = {};
  private pollTimer: ReturnType<typeof setTimeout> | null = null;
  private clock: ReturnType<typeof setInterval> | null = null;
  private startedAt = 0;

  ngOnInit(): void {
    const idParam = this.route.snapshot.queryParamMap.get('id');
    this.returnQuery = idParam ? { id: idParam } : {};
    this.authService.getProfile().subscribe(profile => {
      this.session = { fullName: profile.fullName || profile.email, subtitle: profile.role === 'ADMIN' ? 'مدير النظام' : 'منخرط' };
    });
    const running = this.storedJob();
    if (running) this.follow(running);
  }

  ngOnDestroy(): void {
    this.stopPolling();
    [this.previewUrl, this.pageUrl].forEach(url => url && URL.revokeObjectURL(url));
  }

  protected get running(): boolean {
    return this.job?.status === 'queued' || this.job?.status === 'running';
  }

  // ---------------------------------------------------------------- file
  protected onDragOver(event: DragEvent): void { event.preventDefault(); this.dragging = true; }
  protected onDrop(event: DragEvent): void { event.preventDefault(); this.dragging = false; this.pick(event.dataTransfer?.files?.[0]); }
  protected onFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.pick(input.files?.[0]);
    input.value = '';
  }

  private pick(file: File | undefined): void {
    if (!file || this.running) return;
    if (!file.type.startsWith('image/') && file.type !== 'application/pdf') {
      this.errorMessage = `صورة أو PDF فقط / Image ou PDF uniquement : ${file.name}`;
      return;
    }
    if (file.size > MAX_BYTES) {
      this.errorMessage = `الملف يتجاوز 10 ميغا / Le fichier dépasse 10 Mo : ${file.name}`;
      return;
    }
    this.reset();
    this.file = file;
    this.previewUrl = file.type.startsWith('image/') ? URL.createObjectURL(file) : null;
  }

  protected get fileSize(): string {
    const bytes = this.file?.size ?? 0;
    return bytes < 1024 * 1024 ? `${Math.round(bytes / 1024)} Ko` : `${(bytes / 1024 / 1024).toFixed(1)} Mo`;
  }

  // ---------------------------------------------------------------- analysis
  protected analyse(): void {
    if (!this.file || this.running) return;
    this.errorMessage = null;
    this.analysis.start(this.file).subscribe({
      next: job => {
        this.storeJob(job.id);
        this.follow(job.id, job);
      },
      error: error => { this.errorMessage = this.serviceError(error) ?? httpErrorMessage(error, { ar: 'إرسال الوثيقة للتحليل', fr: "de l'envoi du document à l'analyse" }); }
    });
  }

  /** The backend answers 503 when the document-analysis service is not running. */
  private serviceError(error: unknown): string | null {
    return error instanceof HttpErrorResponse && error.status === 503
      ? "خدمة تحليل الوثائق غير مشغلة، يرجى الاتصال بالمسؤول / Le service d'analyse de document n'est pas démarré : contactez l'administrateur."
      : null;
  }

  private follow(id: string, first?: AnalysisJob): void {
    this.startedAt = Date.now();
    this.elapsed = 0;
    this.clock = setInterval(() => this.elapsed = Math.round((Date.now() - this.startedAt) / 1000), 1000);
    if (first) this.job = first;
    const poll = () => this.analysis.get(id).subscribe({
      next: job => {
        this.job = job;
        if (job.status === 'done' && job.data) this.finish(id, job.data);
        else if (job.status === 'error') this.fail(`تعذر تحليل الوثيقة / Analyse impossible : ${job.error ?? ''}`);
        else this.pollTimer = setTimeout(poll, POLL_MS);
      },
      error: error => this.fail(this.serviceError(error) ?? httpErrorMessage(error, { ar: 'متابعة التحليل', fr: "du suivi de l'analyse" }))
    });
    poll();
  }

  private finish(id: string, data: AnalysisData): void {
    this.stopPolling();
    this.clearJob();
    this.data = structuredClone(data);
    this.analysis.page(id).subscribe({ next: blob => this.pageUrl = URL.createObjectURL(blob), error: () => this.pageUrl = null });
  }

  private fail(message: string): void {
    this.stopPolling();
    this.clearJob();
    this.job = null;
    this.errorMessage = message;
  }

  private stopPolling(): void {
    if (this.pollTimer) clearTimeout(this.pollTimer);
    if (this.clock) clearInterval(this.clock);
    this.pollTimer = this.clock = null;
  }

  protected reset(): void {
    this.stopPolling();
    this.clearJob();
    [this.previewUrl, this.pageUrl].forEach(url => url && URL.revokeObjectURL(url));
    this.file = this.previewUrl = this.pageUrl = this.job = this.data = null;
    this.errorMessage = null;
  }

  // ---------------------------------------------------------------- results
  /** Columns in the order of the paper (right to left), as on the page image. */
  protected get columns(): number[] {
    return (this.data?.table.headers ?? []).map((_, index) => index).reverse();
  }

  protected get toCheck(): number {
    if (!this.data) return 0;
    const cells = this.data.table.rows.flat().filter(cell => cell.text && cell.conf < CONF_MEDIUM).length;
    return cells + this.data.fields.filter(field => field.conf < CONF_MEDIUM).length;
  }

  protected tone(conf: number, text: string): string {
    if (!text) return '';
    if (conf < CONF_MEDIUM) return 'low';
    return conf < CONF_GOOD ? 'medium' : '';
  }

  protected percent(conf: number): string {
    return `${Math.round(conf * 100)}%`;
  }

  protected editField(index: number, key: 'label' | 'value', event: Event): void {
    const field = this.data!.fields[index];
    const value = (event.target as HTMLInputElement).value.trim();
    if (value === field[key]) return;
    field[key] = value;
    field.conf = 1;
    field.note = EDITED;
  }

  protected editCell(row: number, col: number, event: Event): void {
    const cell = this.data!.table.rows[row][col];
    const value = (event.target as HTMLInputElement).value.trim();
    if (value === cell.text) return;
    cell.text = value;
    cell.conf = 1;
    cell.note = EDITED;
  }

  /** Recomputes the member-form values with the corrections, then goes back to the form. */
  protected fillForm(): void {
    if (!this.data) return;
    this.sending = true;
    this.errorMessage = null;
    this.analysis.memberForm(this.data).subscribe({
      next: result => {
        const carried = this.drafts.peek();
        if (carried) {
          carried.ocrResult = result;
        } else {
          // Page opened on its own: the form reopens with only the values read.
          this.drafts.keep({ memberId: this.returnQuery['id'] ? Number(this.returnQuery['id']) : null, returnQuery: this.returnQuery,
            form: null, members: [], marriedSeveralTimes: null, statut: 'actif', pendingFiles: [], ocrResult: result });
        }
        this.router.navigate(['/member'], { queryParams: this.returnQuery });
      },
      error: error => {
        this.sending = false;
        this.errorMessage = httpErrorMessage(error, { ar: 'تحضير بيانات الاستمارة', fr: 'de la préparation des données du formulaire' });
      }
    });
  }

  protected back(): void {
    this.router.navigate(['/member'], { queryParams: this.returnQuery });
  }

  // ---------------------------------------------------------------- running analysis kept across reloads
  private storeJob(id: string): void {
    try { sessionStorage.setItem(JOB_KEY, id); } catch { /* storage unavailable */ }
  }

  private storedJob(): string | null {
    try { return sessionStorage.getItem(JOB_KEY); } catch { return null; }
  }

  private clearJob(): void {
    try { sessionStorage.removeItem(JOB_KEY); } catch { /* storage unavailable */ }
  }
}
