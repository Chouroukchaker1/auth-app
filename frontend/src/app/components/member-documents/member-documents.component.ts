import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { httpErrorMessage } from '../../core/http-errors';
import { MemberDraftService } from '../../core/member-draft.service';
import { MemberService } from '../../core/member.service';
import { SiteFooterComponent } from '../layout/site-footer.component';
import { TopbarComponent } from '../layout/topbar.component';

type BadgeTone = 'financier' | 'administratif' | 'other';

interface DocumentRow {
  name: string;
  type: string;
  tone: BadgeTone;
  size: string;
  date: string;
  /** Saved on the server. */
  docId?: number;
  /** Picked in the form but not saved yet. */
  file?: File;
}

/** Lists the files attached to a member record ("عرض الوثائق" on the member form). */
@Component({
  selector: 'app-member-documents',
  imports: [TopbarComponent, SiteFooterComponent],
  templateUrl: './member-documents.component.html',
  styleUrl: './member-documents.component.scss'
})
export class MemberDocumentsComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly memberService = inject(MemberService);
  private readonly drafts = inject(MemberDraftService);
  private readonly route = inject(ActivatedRoute);

  protected session = { fullName: '', subtitle: '' };
  protected rows: DocumentRow[] = [];
  protected loading = true;
  protected errorMessage: string | null = null;
  protected successMessage: string | null = null;
  protected statut = 'actif';
  private memberId: number | null = null;

  ngOnInit(): void {
    const idParam = this.route.snapshot.queryParamMap.get('id');
    this.memberId = idParam ? Number(idParam) : null;

    const carried = this.drafts.peek();
    const pending = carried && carried.memberId === this.memberId ? carried.pendingFiles : [];
    if (carried) this.statut = carried.statut;

    this.authService.getProfile().subscribe(profile => {
      this.session = {
        fullName: profile.fullName || profile.email,
        subtitle: profile.role === 'ADMIN' ? 'مدير النظام' : 'منخرط'
      };
    });

    // Not saved yet: the date is the PC's, taken when the file was picked.
    const pendingRows = pending.map(({ file, typeFichier, addedAt }) => this.toRow(file.name, typeFichier, file.size, addedAt, { file }));
    if (this.memberId === null) {
      this.rows = pendingRows;
      this.loading = false;
      return;
    }

    this.memberService.getById(this.memberId).subscribe({
      next: member => {
        if (!carried) this.statut = member.statut;
        this.rows = [
          ...(member.documents ?? []).map(doc => this.toRow(doc.filename, doc.typeFichier, doc.size, doc.createdAt, { docId: doc.id })),
          ...pendingRows
        ];
        this.loading = false;
      },
      error: error => {
        this.rows = pendingRows;
        this.loading = false;
        this.errorMessage = httpErrorMessage(error, { ar: 'تحميل الوثائق', fr: 'du chargement des documents' });
      }
    });
  }

  /** Same split as the dashboard tabs: retired members are "Retraités", everyone else "Cadre commun". */
  protected get requestType(): { ar: string; fr: string } {
    return this.statut === 'retraite'
      ? { ar: 'المتقاعدون', fr: 'Retraités' }
      : { ar: 'الإطار المشترك', fr: 'Cadre commun' };
  }

  protected view(row: DocumentRow): void {
    this.errorMessage = null;
    this.successMessage = null;
    if (row.file) {
      window.open(URL.createObjectURL(row.file), '_blank');
      return;
    }
    if (row.docId === undefined || this.memberId === null) return;
    // Open the tab inside the click so the browser does not block it, then fill it.
    const tab = window.open('', '_blank');
    this.memberService.getDocumentBlob(this.memberId, row.docId).subscribe({
      next: blob => {
        const url = URL.createObjectURL(blob);
        if (tab) tab.location.href = url; else window.open(url, '_blank');
      },
      error: error => {
        tab?.close();
        this.errorMessage = httpErrorMessage(error, { ar: 'فتح الوثيقة', fr: "de l'ouverture du document" });
      }
    });
  }

  protected remove(row: DocumentRow): void {
    if (!confirm(`حذف الوثيقة / Supprimer le document ${row.name} ?`)) return;
    this.errorMessage = null;
    this.successMessage = null;

    if (row.file) {
      const carried = this.drafts.peek();
      if (carried) carried.pendingFiles = carried.pendingFiles.filter(pending => pending.file !== row.file);
      this.rows = this.rows.filter(item => item !== row);
      this.successMessage = `تم حذف الوثيقة / Document retiré : ${row.name}`;
      return;
    }
    if (row.docId === undefined || this.memberId === null) return;
    this.memberService.deleteDocument(this.memberId, row.docId).subscribe({
      next: () => {
        this.rows = this.rows.filter(item => item !== row);
        this.successMessage = `تم حذف الوثيقة / Document supprimé : ${row.name}`;
      },
      error: error => { this.errorMessage = httpErrorMessage(error, { ar: 'حذف الوثيقة', fr: 'de la suppression du document' }); }
    });
  }

  private toRow(name: string, typeFichier: string, bytes: number, createdAt: string | null,
                source: Pick<DocumentRow, 'docId' | 'file'>): DocumentRow {
    const types: Record<string, { label: string; tone: BadgeTone }> = {
      financier: { label: 'Financier', tone: 'financier' },
      administratif: { label: 'Administratif', tone: 'administratif' },
      medical: { label: 'Médical', tone: 'other' }
    };
    const type = types[typeFichier] ?? { label: 'Autres', tone: 'other' as BadgeTone };
    return {
      name,
      type: type.label,
      tone: type.tone,
      size: this.humanSize(bytes),
      date: createdAt ? this.formatDate(createdAt) : '—',
      ...source
    };
  }

  private formatDate(iso: string): string {
    const [year, month, day] = iso.slice(0, 10).split('-');
    return `${day}/${month}/${year}`;
  }

  private humanSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} o`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`;
    return `${(bytes / 1024 / 1024).toFixed(1)} Mo`;
  }
}
