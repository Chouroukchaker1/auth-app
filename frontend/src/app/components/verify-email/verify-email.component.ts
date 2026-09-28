import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-verify-email',
  imports: [RouterLink],
  templateUrl: './verify-email.component.html',
  styleUrl: './verify-email.component.scss'
})
export class VerifyEmailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly authService = inject(AuthService);

  protected loading = true;
  protected verified = false;
  protected message = '';

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) {
      this.loading = false;
      this.message = 'Le lien de validation est incomplet.';
      return;
    }

    this.authService.verifyEmail(token).subscribe({
      next: response => {
        this.verified = true;
        this.message = response.message;
        this.loading = false;
      },
      error: response => {
        this.message = response.status === 400
          ? 'Ce lien de validation est invalide ou expiré.'
          : 'La validation de votre adresse email a échoué.';
        this.loading = false;
      }
    });
  }
}