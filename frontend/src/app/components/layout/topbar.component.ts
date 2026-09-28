import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth.service';

/** Dark top navigation bar shared by the signed-in pages (dashboard, member form). */
@Component({
  selector: 'app-topbar',
  imports: [RouterLink],
  templateUrl: './topbar.component.html',
  styleUrl: './topbar.component.scss'
})
export class TopbarComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  @Input() fullName = '';
  @Input() subtitle = '';
  @Input() query = '';
  @Output() readonly search = new EventEmitter<string>();

  protected readonly lastLogin = this.formatLastLogin(this.authService.getLastLogin() ?? new Date());

  protected onInput(event: Event): void {
    this.search.emit((event.target as HTMLInputElement).value);
  }

  protected logout(): void {
    this.authService.logout();
    this.router.navigate(['/auth']);
  }

  private formatLastLogin(date: Date): string {
    const day = date.toLocaleDateString('ar-TN-u-nu-latn', { day: 'numeric', month: 'long', year: 'numeric' });
    const time = date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    return `${day}، الساعة ${time}`;
  }
}
