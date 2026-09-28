import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-auth-page',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './auth-page.component.html',
  styleUrl: './auth-page.component.scss'
})
export class AuthPageComponent implements OnInit {
  private readonly formBuilder = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected mode: 'login' | 'register' = 'login';
  protected loading = false;
  protected error = '';
  protected success = '';
  protected photoFile: File | null = null;
  protected photoPreviewUrl: string | null = null;

  protected readonly form = this.formBuilder.nonNullable.group({
    fullName: [''],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]]
  });

  ngOnInit(): void {
    this.applyMode(this.route.snapshot.data['mode'] === 'register' ? 'register' : 'login');
  }

  protected switchMode(mode: 'login' | 'register'): void {
    this.router.navigate([mode === 'register' ? '/auth/register' : '/auth']);
    this.applyMode(mode);
  }

  private applyMode(mode: 'login' | 'register'): void {
    this.mode = mode;
    this.error = '';
    this.success = '';
    const fullNameControl = this.form.controls.fullName;
    if (mode === 'register') {
      fullNameControl.setValidators([Validators.required]);
    } else {
      fullNameControl.clearValidators();
    }
    fullNameControl.updateValueAndValidity();
    this.form.reset();
    this.photoFile = null;
    this.photoPreviewUrl = null;
  }

  protected onPhoto(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.photoFile = file;
    this.photoPreviewUrl = URL.createObjectURL(file);
  }

  protected submit(): void {
    if (this.form.invalid || this.loading) {
      this.form.markAllAsTouched();
      return;
    }

    this.loading = true;
    this.error = '';
    const { fullName, email, password } = this.form.getRawValue();
    if (this.mode === 'register') {
      this.authService.register(fullName, email, password, this.photoFile)
        .pipe(finalize(() => this.loading = false))
        .subscribe({
          next: response => {
          const message = response.message;
          this.switchMode('login');
          this.success = message;
          },
          error: () => this.error = 'Cet email est peut-être déjà utilisé.'
        });
      return;
    }

    this.authService.login(email, password)
      .pipe(finalize(() => this.loading = false))
      .subscribe({
        next: () => this.router.navigate(['/dashboard']),
        error: response => this.error = response.status === 403
          ? 'Validez votre adresse email avant de vous connecter.'
          : 'Email ou mot de passe incorrect.'
      });
  }
}
 
// Il valide le formulaire, communique avec AuthService et redirige l'utilisateur
// vers le Dashboard après une authentification réussie.