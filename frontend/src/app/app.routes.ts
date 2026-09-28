import { Routes } from '@angular/router';
import { AuthPageComponent } from './components/auth-page/auth-page.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { ForgotPasswordComponent } from './components/forgot-password/forgot-password.component';
import { ResetPasswordComponent } from './components/reset-password/reset-password.component';
import { UserManagementComponent } from './components/user-management/user-management.component';
import { VerifyEmailComponent } from './components/verify-email/verify-email.component';
import { MemberFormComponent } from './components/member-form/member-form.component';
import { MemberDocumentsComponent } from './components/member-documents/member-documents.component';
import { ProfileComponent } from './components/profile/profile.component';
import { LandingPageComponent } from './components/landing-page/landing-page.component';
import { adminGuard } from './core/admin.guard';
import { authGuard } from './core/auth.guard';

export const routes: Routes = [
	{ path: '', pathMatch: 'full', component: LandingPageComponent },
	{ path: 'auth', component: AuthPageComponent },
	{ path: 'auth/register', component: AuthPageComponent, data: { mode: 'register' } },
	{ path: 'forgot-password', component: ForgotPasswordComponent },
	{ path: 'reset-password', component: ResetPasswordComponent },
	{ path: 'verify-email', component: VerifyEmailComponent },
	{ path: 'users', component: UserManagementComponent, canActivate: [adminGuard] },
	{ path: 'dashboard', component: DashboardComponent, canActivate: [authGuard] },
	{ path: 'member', component: MemberFormComponent, canActivate: [authGuard] },
	{ path: 'member/documents', component: MemberDocumentsComponent, canActivate: [authGuard] },
	{ path: 'profile', component: ProfileComponent, canActivate: [authGuard] },
	{ path: '**', redirectTo: '' }
];
//security 
