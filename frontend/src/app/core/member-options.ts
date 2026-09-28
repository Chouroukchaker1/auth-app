export interface Option { value: string; label: string; }

export const SERVICE_TYPES: Option[] = [
  { value: 'public', label: 'المصلحة العمومية / Service public' },
  { value: 'prive', label: 'القطاع الخاص / Secteur privé' },
  { value: 'retraite', label: 'متقاعد / Retraité' }
];

export const GRADES: Option[] = [
  { value: 'mohafedh', label: 'محافظ شرطة' },
  { value: 'motafakkid', label: 'متفقد شرطة' },
  { value: 'malazem', label: 'ملازم أول' },
  { value: 'aaun', label: 'عون شرطة' }
];

export const CITIES: Option[] = [
  { value: 'sousse', label: 'سوسة / Sousse' },
  { value: 'tunis', label: 'تونس / Tunis' },
  { value: 'sfax', label: 'صفاقس / Sfax' },
  { value: 'bizerte', label: 'بنزرت / Bizerte' }
];

export const STATUSES: Option[] = [
  { value: 'actif', label: 'نشط / Actif' },
  { value: 'suspendu', label: 'موقوف / Suspendu' }
];

export const FILE_TYPES: Option[] = [
  { value: 'financier', label: 'ملف مالي / Dossier financier' },
  { value: 'medical', label: 'ملف طبي / Dossier médical' },
  { value: 'administratif', label: 'ملف إداري / Dossier administratif' }
];

export const MARITAL_STATUSES: Option[] = [
  { value: 'marie', label: 'متزوج(ة) / Marié(e)' },
  { value: 'celibataire', label: 'أعزب / Célibataire' },
  { value: 'divorce', label: 'مطلق(ة) / Divorcé(e)' }
];

export const RELATIONS: Option[] = [
  { value: 'epouse', label: 'زوجة / Épouse' },
  { value: 'epoux', label: 'زوج / Époux' },
  { value: 'fils', label: 'الإبن / Fils' },
  { value: 'fille', label: 'الإبنة / Fille' }
];

export function optionLabel(options: Option[], value: string | null | undefined): string {
  return options.find(option => option.value === value)?.label ?? (value ?? '—');
}
