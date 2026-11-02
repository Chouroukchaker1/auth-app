import { Option } from './member-options';

/** A value read on the document, with the model's confidence (0..1). */
export interface ReadField { label: string; value: string; conf: number; note: string; raw: string; }
export interface ReadCell { text: string; conf: number; note: string; raw: string; }

/** Analysis result, as produced by document-analysis/export.py (to_dict). */
export interface AnalysisData {
  source: string;
  seconds: number;
  fields: ReadField[];
  table: { headers: string[]; rows: ReadCell[][] };
  raw_lines: { text: string; conf: number }[];
}

export interface OcrFamilyMember { nom: string; prenom: string; lienParente: string; dateNaissance: string; }

/** Member-form values computed from an analysis (document-analysis/form_link.py). */
export interface OcrResult {
  source: string;
  fields: Partial<Record<
    'nomPrenom' | 'numeroAffiliation' | 'numeroUnifie' | 'cnr' | 'grade'
    | 'dateNaissance' | 'lieuNaissance' | 'debutActivite' | 'dateMariage', string>>;
  family: OcrFamilyMember[];
}

export interface AnalysisJob {
  id: string;
  status: 'queued' | 'running' | 'done' | 'error';
  progress: number;
  message: string;
  error: string | null;
  /** Analyses waiting before this one. */
  position: number;
  pages: number;
  seconds: number | null;
  data: AnalysisData | null;
  memberForm: OcrResult | null;
}

/** Same thresholds as document-analysis/export.py: below MEDIUM the value must be checked. */
export const CONF_GOOD = 0.8;
export const CONF_MEDIUM = 0.55;

/** Arabic-insensitive comparison key: no harakat/tatweel, unified alef/ya/ta marbuta, no spaces. */
function normalize(text: string): string {
  return text
    .replace(/[ً-ْـ]/g, '')
    .replace(/[أإآ]/g, 'ا').replace(/ى/g, 'ي').replace(/ة/g, 'ه')
    .replace(/[\s.\-_:]+/g, '')
    .toLowerCase();
}

/** Option whose Arabic or French label matches the text read on the document. */
export function matchOption(options: Option[], text: string | undefined): Option | null {
  if (!text) return null;
  const read = normalize(text);
  if (read.length < 3) return null;
  return options.find(option => option.label.split(' / ').some(part => {
    const label = normalize(part);
    return label === read || read.includes(label) || label.includes(read);
  })) ?? null;
}
