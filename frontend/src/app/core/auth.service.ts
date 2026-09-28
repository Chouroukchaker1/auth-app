import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

export interface AuthResponse {
  token: string;
}

export interface MessageResponse {
  message: string;
}

export interface User {
  id: number;
  fullName: string;
  email: string;
  role: string;
  hasPhoto: boolean;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = 'http://localhost:8080/api';
  private readonly tokenKey = 'auth_token';
  private readonly lastLoginKey = 'last_login_at';

  register(fullName: string, email: string, password: string, photo?: File | null): Observable<MessageResponse> {
    const form = new FormData();
    form.append('data', new Blob([JSON.stringify({ fullName, email, password })], { type: 'application/json' }));
    if (photo) form.append('photo', photo);
    return this.http.post<MessageResponse>(`${this.apiUrl}/auth/register`, form);
  }

  login(email: string, password: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/auth/login`, { email, password })
      .pipe(tap(response => {
        this.storeToken(response.token);
        localStorage.setItem(this.lastLoginKey, new Date().toISOString());
      }));
  }

  getLastLogin(): Date | null {
    const value = localStorage.getItem(this.lastLoginKey);
    return value ? new Date(value) : null;
  }

  forgotPassword(email: string): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(`${this.apiUrl}/auth/forgot-password`, { email });
  }

  resetPassword(email: string, code: string, newPassword: string): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(`${this.apiUrl}/auth/reset-password`, {
      email,
      code,
      newPassword
    });
  }

  verifyEmail(token: string): Observable<MessageResponse> {
    return this.http.get<MessageResponse>(`${this.apiUrl}/auth/verify-email`, {
      params: { token }
    });
  }

  getProfile(): Observable<{ fullName: string; email: string; role: string; hasPhoto: boolean }> {
    return this.http.get<{ fullName: string; email: string; role: string; hasPhoto: boolean }>(`${this.apiUrl}/me`);
  }

  getMyPhotoBlob(): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/me/photo`, { responseType: 'blob' });
  }

  updateMe(fullName: string, email: string, password: string, photo?: File | null):
      Observable<{ fullName: string; email: string; role: string; hasPhoto: boolean; token: string }> {
    const form = new FormData();
    form.append('data', new Blob([JSON.stringify({ fullName, email, password: password || null })], { type: 'application/json' }));
    if (photo) form.append('photo', photo);
    return this.http.put<{ fullName: string; email: string; role: string; hasPhoto: boolean; token: string }>(
      `${this.apiUrl}/me`, form
    ).pipe(tap(response => this.storeToken(response.token)));
  }

  getUsers(): Observable<User[]> {
    return this.http.get<User[]>(`${this.apiUrl}/users`);
  }

  exportUsersPdf(): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/users/export/pdf`, { responseType: 'blob' });
  }

  exportUsersExcel(): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/users/export/excel`, { responseType: 'blob' });
  }

  createUser(fullName: string, email: string, password: string, role: string, photo?: File | null): Observable<User> {
    const form = new FormData();
    form.append('data', new Blob([JSON.stringify({ fullName, email, password, role })], { type: 'application/json' }));
    if (photo) form.append('photo', photo);
    return this.http.post<User>(`${this.apiUrl}/users`, form);
  }

  getUserPhotoBlob(id: number): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/users/${id}/photo`, { responseType: 'blob' });
  }

  updateUser(id: number, fullName: string, email: string, password: string, role: string): Observable<User> {
    return this.http.put<User>(`${this.apiUrl}/users/${id}`, { fullName, email, password, role });
  }

  deleteUser(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/users/${id}`);
  }

  getToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  isAuthenticated(): boolean {
    return !!this.getToken();
  }

  logout(): void {
    localStorage.removeItem(this.tokenKey);
  }

  private storeToken(token: string): void {
    localStorage.setItem(this.tokenKey, token);
  }
}
