import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, ValidatorFn, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { MAX_FILE_BYTES, MAX_REQUEST_BYTES, httpErrorMessage } from '../../core/http-errors';
import { MemberDraftService, localNow } from '../../core/member-draft.service';
import {
  DocumentDto, FamilyMemberDto, MemberDetail, MemberFormPayload, MemberService
} from '../../core/member.service';
import {
  CITIES, FILE_TYPES, GRADES, MARITAL_STATUSES, Option, RELATIONS, SERVICE_TYPES, STATUSES, optionLabel
} from '../../core/member-options';
import { SiteFooterComponent } from '../layout/site-footer.component';
import { TopbarComponent } from '../layout/topbar.component';

interface CardSlot { key: 'militaire' | 'soins'; labelAr: string; labelFr: string; url: string | null; file: File | null; }
interface Attachment { name: string; size: string; file?: File; docId?: number; addedAt?: string; }
interface FamilyMember { nom: string; prenom: string; lien: string; lienLabel: string; dateNaissance: string; }

const today = (): string => new Date().toISOString().slice(0, 10);

/** Date fields: must not be in the future. */
const notInFuture: ValidatorFn = (control: AbstractControl): ValidationErrors | null =>
  control.value && control.value > today() ? { future: true } : null;

/** The adherent must be at least 18 years old. */
const adult: ValidatorFn = (control: AbstractControl): ValidationErrors | null => {
  if (!control.value) return null;
  const limit = new Date();
  limit.setFullYear(limit.getFullYear() - 18);
  return control.value > limit.toISOString().slice(0, 10) ? { minor: true } : null;
};

@Component({
  selector: 'app-member-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, TopbarComponent, SiteFooterComponent],
  templateUrl: './member-form.component.html',
  styleUrl: './member-form.component.scss'
})
export class MemberFormComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly memberService = inject(MemberService);
  private readonly authService = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly drafts = inject(MemberDraftService);
  /** Unsaved state brought back from the documents page, if any. */
  private carried = this.drafts.take();
  private returnQuery: Record<string, string> = {};

  session = { fullName: '', grade: '' };
  photoUrl: string | null = null;
  photoFile: File | null = null;
  dragging = false;
  editIndex: number | null = null;
  /** Only kept in the local draft: the backend has no field for it yet. */
  marriedSeveralTimes: 'oui' | 'non' | null = null;
  saved = false;
  savedMessage = '';
  loading = true;
  saving = false;
  errorMessage: string | null = null;

  private memberId: number | null = null;
  /** Files already stored on the server, so the required photo/cards check can pass without a new upload. */
  private hasSavedPhoto = false;
  private hasSavedCard: Record<CardSlot['key'], boolean> = { soins: false, militaire: false };
  private originalSnapshot: Omit<MemberFormPayload, 'typeFichier'> | null = null;

  private readonly fieldLabels: Record<string, string> = {
    numeroUnifie: 'الرقم الموحد / Numéro unifié',
    cnr: 'CNR',
    numeroAffiliation: "رقم الإنخراط / Numéro d'affiliation",
    typeService: 'نوع الخدمة / Type de service',
    nomPrenom: 'الاسم واللقب / Nom et prénom',
    grade: 'الرتبة / Grade',
    dateNaissance: 'تاريخ الولادة / Date de naissance',
    lieuNaissance: 'مكان الولادة / Lieu de naissance',
    debutActivite: "انطلاق العمل / Début de l'activité",
    statut: 'الحالة / Statut',
    etatCivil: 'الحالة الإجتماعية / État civil',
    dateMariage: 'تاريخ الزواج / Date du mariage',
    typeFichier: 'نوع الملف / Type de fichier'
  };

  serviceTypes: Option[] = SERVICE_TYPES;
  grades: Option[] = GRADES;
  cities: Option[] = CITIES;
  statuses: Option[] = STATUSES;
  fileTypes: Option[] = FILE_TYPES;
  maritalStatuses: Option[] = MARITAL_STATUSES;
  relations: Option[] = RELATIONS;

  cardSlots: CardSlot[] = [
    { key: 'soins', labelAr: 'بطاقة علاج', labelFr: 'Carte de soins', url: null, file: null },
    { key: 'militaire', labelAr: 'بطاقة عسكرية', labelFr: 'Carte militaire', url: null, file: null }
  ];
  attachments: Attachment[] = [];
  members: FamilyMember[] = [];

  form = this.fb.nonNullable.group({
    personal: this.fb.nonNullable.group({
      numeroUnifie: ['', [Validators.required, Validators.pattern(/^\d{8,15}$/)]],
      cnr: ['', [Validators.required, Validators.pattern(/^CNR-\d{4,10}$/i)]],
      numeroAffiliation: ['', [Validators.required, Validators.pattern(/^\d{4,10}$/)]],
      typeService: ['public', Validators.required]
    }),
    member: this.fb.nonNullable.group({
      nomPrenom: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(100)]],
      grade: ['mohafedh', Validators.required],
      dateNaissance: ['', [Validators.required, notInFuture, adult]],
      lieuNaissance: ['sousse', Validators.required],
      debutActivite: ['', [Validators.required, notInFuture]],
      statut: ['actif', Validators.required]
    }),
    documents: this.fb.nonNullable.group({ typeFichier: ['financier', Validators.required] }),
    familyForm: this.fb.nonNullable.group({
      etatCivil: ['marie', Validators.required],
      dateMariage: ['', notInFuture],
      nom: ['', [Validators.required, Validators.minLength(2)]],
      prenom: ['', [Validators.required, Validators.minLength(2)]],
      lienParente: ['epouse', Validators.required],
      dateNaissance: ['', [Validators.required, notInFuture]]
    })
  });

  ngOnInit(): void {
    const idParam = this.route.snapshot.queryParamMap.get('id');
    this.returnQuery = idParam ? { id: idParam } : {};

    this.authService.getProfile().subscribe(profile => {
      this.session = { fullName: profile.fullName || profile.email, grade: profile.role === 'ADMIN' ? 'مدير النظام' : 'منخرط' };

      if (idParam) {
        this.memberId = Number(idParam);
        this.loadMember(this.memberService.getById(this.memberId));
      } else if (profile.role === 'ADMIN') {
        // Admins use this page to create a brand new adherent record, never
        // a preexisting one — leave the form blank.
        this.loading = false;
        this.afterLoad();
      } else {
        this.loadMember(this.memberService.getMine(), true);
      }
    });
  }

  private loadMember(source: ReturnType<MemberService['getById']>, silentNotFound = false): void {
    this.loading = true;
    source.subscribe({
      next: member => { this.applyMember(member); this.loading = false; this.afterLoad(); },
      error: error => {
        this.loading = false;
        if (silentNotFound && error?.status === 404) {
          this.afterLoad();
          return;
        }
        this.showError(httpErrorMessage(error, { ar: 'تحميل ملف المنخرط', fr: 'du chargement de la fiche adhérent' }));
        if (error?.status === 403 || error?.status === 404) {
          this.router.navigate(['/dashboard']);
        }
      }
    });
  }

  private applyMember(member: MemberDetail): void {
    this.memberId = member.id;
    this.hasSavedPhoto = member.hasPhoto;
    this.hasSavedCard = { soins: member.hasCarteSoins, militaire: member.hasCarteMilitaire };
    this.form.patchValue({
      personal: {
        numeroUnifie: member.numeroUnifie ?? '',
        cnr: member.cnr ?? '',
        numeroAffiliation: member.numeroAffiliation ?? '',
        typeService: member.typeService ?? 'public'
      },
      member: {
        nomPrenom: member.nomPrenom ?? '',
        grade: member.grade ?? 'mohafedh',
        dateNaissance: member.dateNaissance ?? '',
        lieuNaissance: member.lieuNaissance ?? 'sousse',
        debutActivite: member.debutActivite ?? '',
        statut: member.statut ?? 'actif'
      },
      familyForm: {
        etatCivil: member.etatCivil ?? 'marie',
        dateMariage: member.dateMariage ?? ''
      }
    });

    this.members = (member.familyMembers ?? []).map(fm => this.toDisplayFamily(fm));
    this.attachments = (member.documents ?? []).map(doc => this.toDisplayAttachment(doc));

    this.photoUrl = null;
    this.photoFile = null;
    this.cardSlots.forEach(slot => { slot.url = null; slot.file = null; });

    if (member.hasPhoto) {
      this.memberService.getPhotoBlob(member.id).subscribe(blob => this.photoUrl = URL.createObjectURL(blob));
    }
    if (member.hasCarteSoins) {
      this.memberService.getCardBlob(member.id, 'soins').subscribe(blob => {
        const slot = this.cardSlots.find(s => s.key === 'soins');
        if (slot) slot.url = URL.createObjectURL(blob);
      });
    }
    if (member.hasCarteMilitaire) {
      this.memberService.getCardBlob(member.id, 'militaire').subscribe(blob => {
        const slot = this.cardSlots.find(s => s.key === 'militaire');
        if (slot) slot.url = URL.createObjectURL(blob);
      });
    }

    this.captureSnapshot();
  }

  private captureSnapshot(): void {
    const raw = this.form.getRawValue();
    this.originalSnapshot = {
      numeroUnifie: raw.personal.numeroUnifie,
      cnr: raw.personal.cnr,
      numeroAffiliation: raw.personal.numeroAffiliation,
      typeService: raw.personal.typeService,
      nomPrenom: raw.member.nomPrenom,
      grade: raw.member.grade,
      dateNaissance: raw.member.dateNaissance,
      lieuNaissance: raw.member.lieuNaissance,
      debutActivite: raw.member.debutActivite,
      statut: raw.member.statut,
      etatCivil: raw.familyForm.etatCivil,
      dateMariage: raw.familyForm.dateMariage || null,
      familyMembers: this.members.map(m => ({ nom: m.nom, prenom: m.prenom, lienParente: m.lien, dateNaissance: m.dateNaissance }))
    };
  }

  private describeChanges(payload: MemberFormPayload, files: { photo?: File | null; carteSoins?: File | null; carteMilitaire?: File | null; documents?: File[] }): string[] {
    const changed: string[] = [];
    const before = this.originalSnapshot;
    if (before) {
      (Object.keys(this.fieldLabels)).forEach(key => {
        if ((before as any)[key] !== (payload as any)[key]) {
          changed.push(this.fieldLabels[key]);
        }
      });
      if (JSON.stringify(before.familyMembers) !== JSON.stringify(payload.familyMembers)) {
        changed.push('أفراد العائلة / Membres de la famille');
      }
    }
    if (files.photo) changed.push('صورة المنخرط / Photo');
    if (files.carteSoins) changed.push('بطاقة علاج / Carte de soins');
    if (files.carteMilitaire) changed.push('بطاقة عسكرية / Carte militaire');
    if (files.documents && files.documents.length) changed.push('الوثائق / Documents');
    return changed;
  }

  private toDisplayFamily(fm: FamilyMemberDto): FamilyMember {
    return { nom: fm.nom, prenom: fm.prenom, lien: fm.lienParente, lienLabel: optionLabel(this.relations, fm.lienParente).split(' /')[0], dateNaissance: fm.dateNaissance };
  }

  private toDisplayAttachment(doc: DocumentDto): Attachment {
    return { name: doc.filename, size: this.humanSize(doc.size), docId: doc.id };
  }

  onPhoto(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      this.showError(`الصورة يجب أن تكون ملف صورة (JPG، PNG) / La photo doit être une image (JPG, PNG) : ${file.name}`);
      return;
    }
    if (!this.checkSize(file)) return;
    this.errorMessage = null;
    this.photoFile = file;
    this.photoUrl = URL.createObjectURL(file);
  }

  onCard(slot: CardSlot, event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    if (!file.type.startsWith('image/') && file.type !== 'application/pdf') {
      this.showError(`${slot.labelAr} : صورة أو PDF فقط / ${slot.labelFr} : image ou PDF uniquement (${file.name})`);
      return;
    }
    if (!this.checkSize(file)) return;
    this.errorMessage = null;
    slot.file = file;
    slot.url = URL.createObjectURL(file);
  }

  onDragOver(event: DragEvent): void { event.preventDefault(); this.dragging = true; }
  onDrop(event: DragEvent): void { event.preventDefault(); this.dragging = false; this.pushFiles(event.dataTransfer?.files); }
  onDocs(event: Event): void { this.pushFiles((event.target as HTMLInputElement).files); (event.target as HTMLInputElement).value = ''; }

  private pushFiles(list?: FileList | null): void {
    if (!list || !list.length) return;
    const accepted = Array.from(list).filter(file => {
      if (file.size === 0) {
        this.showError(`الملف فارغ / Fichier vide : ${file.name}`);
        return false;
      }
      return this.checkSize(file);
    });
    if (accepted.length === list.length) this.errorMessage = null;
    const addedAt = localNow();
    accepted.forEach(file => this.attachments.push({ name: file.name, size: this.humanSize(file.size), file, addedAt }));
  }

  /** Per-file backend limit (10 Mo). */
  private checkSize(file: File): boolean {
    if (file.size <= MAX_FILE_BYTES) return true;
    this.showError(`الملف ${file.name} يتجاوز 10 ميغا / Le fichier ${file.name} dépasse 10 Mo (${this.humanSize(file.size)}).`);
    return false;
  }

  /** Shows the error banner and brings it into view. */
  private showError(message: string): void {
    this.saved = false;
    this.errorMessage = message;
    setTimeout(() => document.querySelector('.member-page .error')?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
  }

  /** Message shown under a field once it has been touched and is invalid. */
  fieldError(path: string): string | null {
    const control = this.form.get(path);
    if (!control || !control.invalid || !(control.touched || control.dirty)) return null;
    const errors = control.errors ?? {};
    if (errors['required']) return 'هذا الحقل إجباري / Champ obligatoire';
    if (errors['pattern']) {
      if (path.endsWith('cnr')) return 'الصيغة المطلوبة / Format attendu : CNR-123456';
      if (path.endsWith('numeroUnifie')) return 'من 8 إلى 15 رقمًا / 8 à 15 chiffres';
      return 'من 4 إلى 10 أرقام / 4 à 10 chiffres';
    }
    if (errors['minlength']) return `${errors['minlength'].requiredLength} أحرف على الأقل / Au moins ${errors['minlength'].requiredLength} caractères`;
    if (errors['maxlength']) return `${errors['maxlength'].requiredLength} حرفًا كحد أقصى / ${errors['maxlength'].requiredLength} caractères maximum`;
    if (errors['future']) return 'التاريخ لا يمكن أن يكون في المستقبل / La date ne peut pas être dans le futur';
    if (errors['minor']) return "يجب أن يكون عمر المنخرط 18 سنة على الأقل / L'adhérent doit avoir au moins 18 ans";
    if (errors['beforeBirth']) return 'يجب أن يكون بعد تاريخ الولادة / Doit être après la date de naissance';
    return 'قيمة غير صالحة / Valeur invalide';
  }

  private humanSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }


  private get familyForm() { return this.form.controls.familyForm; }

  private readonly familyFieldLabels: Record<string, string> = {
    nom: 'الاسم / Nom',
    prenom: 'اللقب / Prénom',
    lienParente: 'الصفة / Lien de parenté',
    dateNaissance: 'تاريخ الولادة / Date de naissance'
  };

  /** Same split as the dashboard tabs: retired members are "Retraités", everyone else "Cadre commun". */
  get requestType(): { ar: string; fr: string } {
    return this.form.controls.member.controls.statut.value === 'retraite'
      ? { ar: 'المتقاعدون', fr: 'Retraités' }
      : { ar: 'الإطار المشترك', fr: 'Cadre commun' };
  }

  /** Splits an "arabic / french" option label into its two halves. */
  splitLabel(label: string): { ar: string; fr: string } {
    const [ar, fr = ''] = label.split(' / ');
    return { ar, fr };
  }

  addMember(): void {
    const group = this.familyForm;
    const requiredKeys: ('nom' | 'prenom' | 'lienParente' | 'dateNaissance')[] = ['nom', 'prenom', 'lienParente', 'dateNaissance'];
    const missing = requiredKeys.filter(key => group.controls[key].invalid);
    if (missing.length) {
      requiredKeys.forEach(key => group.controls[key].markAsTouched());
      this.showError(`يرجى تصحيح الحقول التالية / Veuillez corriger : ${missing.map(key => this.familyFieldLabels[key]).join('، ')}`);
      return;
    }
    const value = group.getRawValue();
    const isSpouse = value.lienParente === 'epouse' || value.lienParente === 'epoux';
    if (isSpouse && this.form.controls.familyForm.controls.etatCivil.value === 'celibataire') {
      this.showError("لا يمكن إضافة زوج(ة) لمنخرط أعزب / Impossible d'ajouter un conjoint : état civil « Célibataire ».");
      return;
    }
    const duplicate = this.members.some((m, i) => i !== this.editIndex
      && m.nom.trim() === value.nom.trim() && m.prenom.trim() === value.prenom.trim() && m.dateNaissance === value.dateNaissance);
    if (duplicate) {
      this.showError('هذا الفرد مضاف مسبقًا / Ce membre de la famille est déjà dans la liste.');
      return;
    }
    this.errorMessage = null;
    const label = optionLabel(this.relations, value.lienParente).split(' /')[0];
    const entry: FamilyMember = {
      nom: value.nom ?? '',
      prenom: value.prenom ?? '',
      lien: value.lienParente ?? '',
      lienLabel: label,
      dateNaissance: value.dateNaissance ?? ''
    };
    if (this.editIndex === null) this.members.push(entry); else { this.members[this.editIndex] = entry; this.editIndex = null; }
    group.patchValue({ nom: '', prenom: '', dateNaissance: '' });
    [group.controls.nom, group.controls.prenom, group.controls.dateNaissance].forEach(control => control.markAsUntouched());
  }

  editMember(index: number): void {
    const member = this.members[index];
    this.familyForm.patchValue({ nom: member.nom, prenom: member.prenom, lienParente: member.lien, dateNaissance: member.dateNaissance });
    this.editIndex = index;
  }

  removeMember(index: number): void { this.members.splice(index, 1); if (this.editIndex === index) this.editIndex = null; }

  save(): void {
    // Drop errors set by a previous attempt (beforeBirth, required marriage date) before checking again.
    this.form.controls.member.controls.debutActivite.updateValueAndValidity();
    this.form.controls.familyForm.controls.dateMariage.updateValueAndValidity();
    const coreGroups = [this.form.controls.personal, this.form.controls.member, this.form.controls.documents];
    const missing: string[] = [];
    coreGroups.forEach(group => {
      Object.keys(group.controls).forEach(key => {
        if ((group.controls as any)[key].invalid) {
          missing.push(this.fieldLabels[key] ?? key);
        }
      });
    });
    const raw = this.form.getRawValue();
    const family = this.form.controls.familyForm.controls;
    if (raw.familyForm.etatCivil === 'marie' && !raw.familyForm.dateMariage) {
      family.dateMariage.setErrors({ required: true });
    }
    const afterBirth = (date: string) => !date || !raw.member.dateNaissance || date > raw.member.dateNaissance;
    if (!afterBirth(raw.member.debutActivite)) {
      this.form.controls.member.controls.debutActivite.setErrors({ beforeBirth: true });
      missing.push(this.fieldLabels['debutActivite']);
    }
    if (raw.familyForm.etatCivil === 'marie' && !afterBirth(raw.familyForm.dateMariage)) {
      family.dateMariage.setErrors({ beforeBirth: true });
    }
    if (family.dateMariage.invalid) {
      family.dateMariage.markAsTouched();
      missing.push(this.fieldLabels['dateMariage']);
    }

    if (!this.photoFile && !this.hasSavedPhoto) missing.push('صورة المنخرط / Photo');
    this.cardSlots.forEach(slot => {
      if (!slot.file && !this.hasSavedCard[slot.key]) missing.push(`${slot.labelAr} / ${slot.labelFr}`);
    });

    if (missing.length) {
      coreGroups.forEach(group => group.markAllAsTouched());
      this.showError(`يرجى تصحيح الحقول التالية لتتمكن من الحفظ / Veuillez corriger : ${[...new Set(missing)].join('، ')}`);
      return;
    }

    const payload: MemberFormPayload = {
      numeroUnifie: raw.personal.numeroUnifie,
      cnr: raw.personal.cnr,
      numeroAffiliation: raw.personal.numeroAffiliation,
      typeService: raw.personal.typeService,
      nomPrenom: raw.member.nomPrenom,
      grade: raw.member.grade,
      dateNaissance: raw.member.dateNaissance,
      lieuNaissance: raw.member.lieuNaissance,
      debutActivite: raw.member.debutActivite,
      statut: raw.member.statut,
      etatCivil: raw.familyForm.etatCivil,
      dateMariage: raw.familyForm.dateMariage || null,
      typeFichier: raw.documents.typeFichier,
      familyMembers: this.members.map(m => ({ nom: m.nom, prenom: m.prenom, lienParente: m.lien, dateNaissance: m.dateNaissance }))
    };

    const files = {
      photo: this.photoFile,
      carteSoins: this.cardSlots.find(s => s.key === 'soins')?.file ?? null,
      carteMilitaire: this.cardSlots.find(s => s.key === 'militaire')?.file ?? null,
      documents: this.attachments.filter(a => a.file).map(a => a.file as File)
    };

    const totalBytes = [files.photo, files.carteSoins, files.carteMilitaire, ...files.documents]
      .reduce((sum, file) => sum + (file?.size ?? 0), 0);
    if (totalBytes > MAX_REQUEST_BYTES) {
      this.showError(`مجموع الملفات يتجاوز 30 ميغا / Le total des fichiers (${this.humanSize(totalBytes)}) dépasse 30 Mo : retirez des documents.`);
      return;
    }

    const wasEdit = this.memberId !== null;
    const changedLabels = wasEdit ? this.describeChanges(payload, files) : [];

    this.saving = true;
    this.errorMessage = null;
    const request = this.memberId
      ? this.memberService.update(this.memberId, payload, files)
      : this.memberService.create(payload, files);

    request.subscribe({
      next: member => {
        this.clearDraft();
        this.applyMember(member);
        this.saving = false;
        this.errorMessage = null;
        this.saved = true;
        this.savedMessage = wasEdit
          ? (changedLabels.length
              ? `تم تعديل : ${changedLabels.join('، ')} / Modifié : ${changedLabels.join(', ')}`
              : 'تم الحفظ، لم يتم رصد أي تغيير / Enregistré, aucun changement détecté.')
          : 'تم حفظ الملف بنجاح / Dossier enregistré avec succès.';
      },
      error: response => {
        this.saving = false;
        this.showError(httpErrorMessage(response, { ar: 'حفظ الملف', fr: "de l'enregistrement de la fiche" }));
      }
    });
  }

  private get draftKey(): string {
    return `member_draft_${this.memberId ?? 'new'}`;
  }

  /** Once the record (or a blank form) is loaded: bring back unsaved state. */
  private afterLoad(): void {
    const carried = this.carried;
    this.carried = null;
    if (!carried || carried.memberId !== this.memberId) {
      this.restoreDraft();
      return;
    }
    this.form.patchValue(carried.form as ReturnType<MemberFormComponent['form']['getRawValue']>);
    this.members = carried.members as FamilyMember[];
    this.marriedSeveralTimes = carried.marriedSeveralTimes;
    carried.pendingFiles.forEach(({ file, addedAt }) => this.attachments.push({ name: file.name, size: this.humanSize(file.size), file, addedAt }));
  }

  /** Opens the attached-files page, keeping everything not yet saved. */
  openDocuments(): void {
    const raw = this.form.getRawValue();
    this.drafts.keep({
      memberId: this.memberId,
      returnQuery: this.returnQuery,
      form: raw,
      members: this.members,
      marriedSeveralTimes: this.marriedSeveralTimes,
      statut: raw.member.statut,
      pendingFiles: this.attachments
        .filter(attachment => attachment.file)
        .map(attachment => ({ file: attachment.file as File, typeFichier: raw.documents.typeFichier, addedAt: attachment.addedAt ?? localNow() }))
    });
    this.router.navigate(['/member/documents'], { queryParams: this.memberId ? { id: this.memberId } : {} });
  }

  saveDraft(): void {
    const draft = {
      form: this.form.getRawValue(),
      members: this.members,
      marriedSeveralTimes: this.marriedSeveralTimes
    };
    try {
      localStorage.setItem(this.draftKey, JSON.stringify(draft));
      this.errorMessage = null;
      this.saved = true;
      this.savedMessage = 'تم حفظ المسودة على هذا الجهاز (بدون الملفات) / Brouillon enregistré sur cet appareil (sans les fichiers).';
    } catch {
      this.showError("تعذر حفظ المسودة في هذا المتصفح / Impossible d'enregistrer le brouillon dans ce navigateur.");
    }
  }

  private restoreDraft(): void {
    let draft: { form: ReturnType<MemberFormComponent['form']['getRawValue']>; members: FamilyMember[]; marriedSeveralTimes: 'oui' | 'non' | null } | null = null;
    try {
      const raw = localStorage.getItem(this.draftKey);
      draft = raw ? JSON.parse(raw) : null;
    } catch {
      draft = null;
    }
    if (!draft) return;
    this.form.patchValue(draft.form);
    this.members = draft.members ?? [];
    this.marriedSeveralTimes = draft.marriedSeveralTimes ?? null;
    this.saved = true;
    this.savedMessage = 'تم استرجاع المسودة / Brouillon restauré.';
  }

  private clearDraft(): void {
    try { localStorage.removeItem(this.draftKey); } catch { /* storage unavailable */ }
  }

  toggleMarried(value: 'oui' | 'non'): void {
    this.marriedSeveralTimes = this.marriedSeveralTimes === value ? null : value;
  }

  cancel(): void {
    this.clearDraft();
    this.marriedSeveralTimes = null;
    if (this.memberId) {
      this.loadMember(this.memberService.getById(this.memberId));
      this.saved = false;
      return;
    }
    this.form.reset({
      personal: { typeService: 'public' },
      member: { grade: 'mohafedh', lieuNaissance: 'sousse', statut: 'actif' },
      documents: { typeFichier: 'financier' },
      familyForm: { etatCivil: 'marie', lienParente: 'epouse' }
    });
    this.members = [];
    this.attachments = [];
    this.errorMessage = null;
    this.photoUrl = null;
    this.photoFile = null;
    this.cardSlots.forEach(slot => { slot.url = null; slot.file = null; });
    this.saved = false;
  }
}
