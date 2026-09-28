import { Component, OnInit, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService, User } from '../../core/auth.service';

@Component({
  selector: 'app-user-management',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './user-management.component.html',
  styleUrl: './user-management.component.scss'
})
export class UserManagementComponent implements OnInit {
  private readonly formBuilder = inject(FormBuilder);
  private readonly authService = inject(AuthService);

  protected users: User[] = [];
  protected editingId: number | null = null;
  protected loading = true;
  protected saving = false;
  protected error = '';
  protected success = '';

  protected readonly form = this.formBuilder.nonNullable.group({
    fullName: ['', [Validators.required, Validators.maxLength(255)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.minLength(8)]],
    role: ['USER', [Validators.required]]
  });

  ngOnInit(): void {
    this.loadUsers();
  }

  protected loadUsers(): void {
    this.loading = true;
    this.authService.getUsers().pipe(finalize(() => this.loading = false)).subscribe({
      next: users => this.users = users,
      error: () => this.error = 'Impossible de charger les utilisateurs.'
    });
  }

  protected startCreate(): void {
    this.editingId = null;
    this.error = '';
    this.success = '';
    this.form.reset({ fullName: '', email: '', password: '', role: 'USER' });
  }

  protected startEdit(user: User): void {
    this.editingId = user.id;
    this.error = '';
    this.success = '';
    this.form.reset({ fullName: user.fullName, email: user.email, password: '', role: user.role });
  }

  protected cancelEdit(): void {
    this.startCreate();
  }

  protected submit(): void {
    if (this.form.invalid || this.saving) {
      this.form.markAllAsTouched();
      return;
    }

    const { fullName, email, password, role } = this.form.getRawValue();
    if (this.editingId === null && !password) {
      this.form.controls.password.setErrors({ required: true });
      this.form.controls.password.markAsTouched();
      return;
    }

    this.saving = true;
    this.error = '';
    this.success = '';
    const request = this.editingId === null
      ? this.authService.createUser(fullName, email, password, role)
      : this.authService.updateUser(this.editingId, fullName, email, password, role);

    request.pipe(finalize(() => this.saving = false)).subscribe({
      next: () => {
        this.success = this.editingId === null
          ? 'Utilisateur créé avec succès.'
          : 'Utilisateur modifié avec succès.';
        this.startCreate();
        this.loadUsers();
      },
      error: response => {
        this.error = response.status === 409
          ? 'Cet email est déjà utilisé.'
          : 'Impossible d’enregistrer cet utilisateur.';
      }
    });
  }

  protected remove(user: User): void {
    if (!confirm(`Supprimer l'utilisateur ${user.fullName} ?`)) {
      return;
    }

    this.error = '';
    this.authService.deleteUser(user.id).subscribe({
      next: () => {
        this.success = 'Utilisateur supprimé avec succès.';
        this.users = this.users.filter(item => item.id !== user.id);
        if (this.editingId === user.id) {
          this.startCreate();
        }
      },
      error: () => this.error = 'Impossible de supprimer cet utilisateur.'
    });
  }

  protected exportExcel(): void {
    this.authService.exportUsersExcel().subscribe({
      next: file => this.downloadFile(file, 'utilisateurs.xlsx'),
      error: () => this.error = 'Impossible de générer le fichier Excel.'
    });
  }

  protected exportPdf(): void {
    this.authService.exportUsersPdf().subscribe({
      next: file => this.downloadFile(file, 'utilisateurs.pdf'),
      error: () => this.error = 'Impossible de générer le fichier PDF.'
    });
  }

  private downloadFile(file: Blob, filename: string): void {
    const url = URL.createObjectURL(file);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }
}
