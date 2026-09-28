import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AuthService } from './auth.service';

export const adminGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (!authService.isAuthenticated()) {
    return router.createUrlTree(['/auth']);
  }

  return authService.getProfile().pipe(
    map(profile => profile.role === 'ADMIN'
      ? true
      : router.createUrlTree(['/dashboard'])),
    catchError(() => of(router.createUrlTree(['/auth'])))
  );
};