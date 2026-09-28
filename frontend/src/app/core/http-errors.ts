import { HttpErrorResponse } from '@angular/common/http';

/** Upload limits enforced by the backend (spring.servlet.multipart.*). */
export const MAX_FILE_BYTES = 10 * 1024 * 1024;
export const MAX_REQUEST_BYTES = 30 * 1024 * 1024;

/**
 * Turns an HTTP error into a bilingual message for the user.
 * `fallback` describes what failed, with its preposition ("du chargement des documents", ...).
 */
export function httpErrorMessage(error: unknown, fallback: { ar: string; fr: string }): string {
  const response = error instanceof HttpErrorResponse ? error : null;
  const status = response?.status ?? -1;
  const serverMessage = typeof response?.error?.message === 'string' ? response.error.message : '';

  switch (status) {
    case 0:
      return 'تعذر الاتصال بالخادم، تحقق من الشبكة ثم أعد المحاولة / Serveur injoignable : vérifiez votre connexion puis réessayez.';
    case 400:
      return `البيانات المرسلة غير صالحة / Données invalides${serverMessage ? ' : ' + serverMessage : '.'}`;
    case 401:
      return 'انتهت صلاحية الجلسة، يرجى تسجيل الدخول من جديد / Session expirée : veuillez vous reconnecter.';
    case 403:
      return 'ليس لديك صلاحية القيام بهذه العملية / Accès refusé : vous n\'avez pas les droits pour cette action.';
    case 404:
      return `العنصر المطلوب غير موجود / Introuvable${serverMessage ? ' : ' + serverMessage : '.'}`;
    case 409:
      return `تعارض في البيانات / Conflit${serverMessage ? ' : ' + serverMessage : '.'}`;
    case 413:
      return 'حجم الملفات كبير جدًا (10 ميغا للملف، 30 ميغا للمجموع) / Fichiers trop volumineux : 10 Mo par fichier, 30 Mo au total.';
    default:
      if (status >= 500) {
        return `خطأ في الخادم أثناء ${fallback.ar}، أعد المحاولة لاحقًا / Erreur serveur lors ${fallback.fr}, réessayez plus tard.`;
      }
      return `حدث خطأ أثناء ${fallback.ar} / Erreur lors ${fallback.fr}${serverMessage ? ' : ' + serverMessage : '.'}`;
  }
}
