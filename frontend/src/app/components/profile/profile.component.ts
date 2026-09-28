import { Component, OnInit, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-profile',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss'
})
export class ProfileComponent implements OnInit {
  private readonly formBuilder = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  protected loading = true;
  protected saving = false;
  protected error = '';
  protected success = '';
  protected photoFile: File | null = null;
  protected photoPreviewUrl: string | null = null;

  protected readonly form = this.formBuilder.nonNullable.group({
    fullName: ['', [Validators.required, Validators.maxLength(255)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.minLength(8)]]
  });

  ngOnInit(): void {
    this.authService.getProfile().subscribe({
      next: profile => {
        this.form.patchValue({ fullName: profile.fullName, email: profile.email });
        if (profile.hasPhoto) {
          this.authService.getMyPhotoBlob().subscribe(blob => this.photoPreviewUrl = URL.createObjectURL(blob));
        }
        this.loading = false;
      },
      error: () => this.loading = false
    });
  }

  protected onPhoto(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.photoFile = file;
    this.photoPreviewUrl = URL.createObjectURL(file);
  }

  protected submit(): void {
    if (this.form.invalid || this.saving) {
      this.form.markAllAsTouched();
      return;
    }

    this.saving = true;
    this.error = '';
    this.success = '';
    const { fullName, email, password } = this.form.getRawValue();

    this.authService.updateMe(fullName, email, password, this.photoFile)
      .pipe(finalize(() => this.saving = false))
      .subscribe({
        next: () => {
          this.success = 'Profil mis à jour avec succès.';
          this.photoFile = null;
          this.form.controls.password.reset('');
        },
        error: response => this.error = response.status === 409
          ? 'Cet email est déjà utilisé.'
          : 'Impossible de mettre à jour le profil.'
      });
  }

  protected cancel(): void {
    this.router.navigate(['/dashboard']);
  }
}
