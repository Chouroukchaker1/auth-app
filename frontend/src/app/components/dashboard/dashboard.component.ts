import { Component, OnInit, inject } from '@angular/core';
import { Router } from '@angular/router';
import { RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { AuthService } from '../../core/auth.service';
import { httpErrorMessage } from '../../core/http-errors';
import { MemberService, MemberSummary } from '../../core/member.service';
import { GRADES, STATUSES, optionLabel } from '../../core/member-options';
import { SiteFooterComponent } from '../layout/site-footer.component';
import { TopbarComponent } from '../layout/topbar.component';

type Category = 'cadre' | 'securite' | 'retraites' | 'brouillons';

interface DisplayUser {
  id: number;
  fullName: string;
  cin: string;
  numeroUnique: string;
  numeroAdhesion: string;
  grade: string;
  statut: string;
  status: 'active' | 'inactive';
  category: Category;
}

const PAGE_SIZE = 10;

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink, TopbarComponent, SiteFooterComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly memberService = inject(MemberService);
  private readonly router = inject(Router);
  protected fullName = '';
  protected email = '';
  protected subtitle = '';
  protected isAdmin = false;
  protected loading = true;
  protected users: DisplayUser[] = [];
  protected removingId: number | null = null;
  protected errorMessage: string | null = null;
  protected successMessage: string | null = null;

  protected readonly statuses = STATUSES;
  protected readonly tabs: { key: Category; ar: string; fr: string }[] = [
    { key: 'cadre', ar: 'الإطار المشترك', fr: 'Cadre commun' },
    { key: 'securite', ar: 'الأمن المباشر', fr: 'Sécurité active' },
    { key: 'retraites', ar: 'المتقاعدون', fr: 'Retraités' },
    { key: 'brouillons', ar: 'المسودات', fr: 'Brouillons' }
  ];
  protected activeTab: Category = 'cadre';
  protected statusFilter = '';
  protected query = '';
  protected page = 1;

  ngOnInit(): void {
    this.authService.getProfile().subscribe({
      next: profile => {
        this.fullName = profile.fullName || profile.email;
        this.email = profile.email;
        this.isAdmin = profile.role === 'ADMIN';
        this.subtitle = this.isAdmin ? 'مدير النظام' : 'منخرط';
        this.loadMembers();
      },
      error: () => this.logout()
    });
  }

  protected count(category: Category): number {
    return this.users.filter(user => user.category === category).length;
  }

  protected get filteredUsers(): DisplayUser[] {
    const query = this.query.trim().toLowerCase();
    return this.users.filter(user =>
      user.category === this.activeTab
      && (!this.statusFilter || user.statut === this.statusFilter)
      && (!query || [user.fullName, user.cin, user.numeroUnique, user.numeroAdhesion]
        .some(value => value.toLowerCase().includes(query)))
    );
  }

  protected get pageCount(): number {
    return Math.max(1, Math.ceil(this.filteredUsers.length / PAGE_SIZE));
  }

  protected get pagedUsers(): DisplayUser[] {
    const start = (this.page - 1) * PAGE_SIZE;
    return this.filteredUsers.slice(start, start + PAGE_SIZE);
  }

  /** Page numbers to show, with 0 standing for an ellipsis. */
  protected get pages(): number[] {
    const total = this.pageCount;
    if (total <= 9) {
      return Array.from({ length: total }, (_, i) => i + 1);
    }
    const head = this.page <= 6 ? [1, 2, 3, 4, 5, 6, 7] : [1, 0, this.page - 2, this.page - 1, this.page, this.page + 1, this.page + 2];
    const visible = head.filter(n => n < total);
    return visible[visible.length - 1] < total - 1 ? [...visible, 0, total] : [...visible, total];
  }

  protected selectTab(tab: Category): void {
    this.activeTab = tab;
    this.page = 1;
  }

  protected onQuery(event: Event): void {
    this.setQuery((event.target as HTMLInputElement).value);
  }

  protected setQuery(value: string): void {
    this.query = value;
    this.page = 1;
  }

  protected onStatus(event: Event): void {
    this.statusFilter = (event.target as HTMLSelectElement).value;
    this.page = 1;
  }

  protected goTo(page: number | string): void {
    const target = Math.round(Number(page));
    if (target >= 1 && target <= this.pageCount) {
      this.page = target;
    }
  }

  private loadMembers(): void {
    const source = this.isAdmin
      ? this.memberService.list()
      : this.memberService.getMine().pipe(
          map(member => {
            this.subtitle = optionLabel(GRADES, member.grade);
            return [{
              id: member.id,
              nomPrenom: member.nomPrenom,
              dateNaissance: member.dateNaissance,
              numeroUnifie: member.numeroUnifie,
              numeroAffiliation: member.numeroAffiliation,
              grade: member.grade,
              statut: member.statut
            } as MemberSummary];
          }),
          catchError(error => error instanceof HttpErrorResponse && error.status === 404
            ? of([] as MemberSummary[])
            : throwError(() => error))
        );

    source.subscribe({
      next: summaries => {
        this.users = summaries.length
          ? summaries.map(summary => this.toDisplayUser(summary))
          : (this.isAdmin ? [] : [{
              id: 0, fullName: this.fullName, cin: '—', numeroUnique: '—', numeroAdhesion: '—',
              grade: '—', statut: 'actif', status: 'active', category: 'cadre'
            }]);
        this.loading = false;
      },
      error: error => {
        this.loading = false;
        if (error?.status === 401) { this.logout(); return; }
        this.errorMessage = httpErrorMessage(error, { ar: 'تحميل قائمة المنخرطين', fr: 'du chargement des adhérents' });
      }
    });
  }

  private toDisplayUser(summary: MemberSummary): DisplayUser {
    return {
      id: summary.id,
      fullName: summary.nomPrenom,
      cin: '—',
      numeroUnique: summary.numeroUnifie || '—',
      numeroAdhesion: summary.numeroAffiliation || '—',
      grade: optionLabel(GRADES, summary.grade),
      statut: summary.statut,
      status: summary.statut === 'actif' ? 'active' : 'inactive',
      category: summary.statut === 'retraite' ? 'retraites' : 'cadre'
    };
  }

  protected logout(): void {
    this.authService.logout();
    this.router.navigate(['/auth']);
  }

  protected removeUser(user: DisplayUser): void {
    if (!this.isAdmin || user.id === 0 || !confirm(`حذف المنخرط / Supprimer l'adhérent ${user.fullName} ?`)) {
      return;
    }

    this.removingId = user.id;
    this.errorMessage = null;
    this.successMessage = null;
    this.memberService.delete(user.id).subscribe({
      next: () => {
        this.users = this.users.filter(item => item.id !== user.id);
        this.goTo(Math.min(this.page, this.pageCount));
        this.removingId = null;
        this.successMessage = `تم حذف المنخرط / Adhérent supprimé : ${user.fullName}`;
      },
      error: error => {
        this.removingId = null;
        this.errorMessage = httpErrorMessage(error, { ar: 'حذف المنخرط', fr: "de la suppression de l'adhérent" });
      }
    });
  }
}
