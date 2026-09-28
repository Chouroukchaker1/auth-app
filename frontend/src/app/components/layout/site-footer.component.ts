import { Component } from '@angular/core';

/** Dark footer shared by the signed-in pages (dashboard, member form). */
@Component({
  selector: 'app-site-footer',
  template: `
    <footer class="site-footer" dir="rtl">
      <span>تعاونية سلك أمن رئيس الدولة والشخصيات الرسمية</span>
      <span class="footer-divider" aria-hidden="true"></span>
      <span>جميع الحقوق محفوظة <span class="footer-year">© 2026</span></span>
    </footer>
  `,
  styles: `
    :host { display: block; }

    .site-footer {
      height: 60px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 10px 24px;
      background: #054a63;
      color: #ffffff;
      font-family: 'Noto Sans Arabic', sans-serif;
      font-size: 16px;
      font-weight: 500;
      line-height: 24px;
      text-align: center;
    }

    .site-footer > span:not(.footer-divider) {
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }

    .footer-divider {
      width: 1.5px;
      height: 18px;
      background: currentColor;
    }

    .footer-year { font-family: 'Manrope', sans-serif; }

    @media (max-width: 700px) {
      .site-footer { height: auto; flex-direction: column; gap: 2px; font-size: 14px; }
      .footer-divider { display: none; }
    }
  `
})
export class SiteFooterComponent {}
