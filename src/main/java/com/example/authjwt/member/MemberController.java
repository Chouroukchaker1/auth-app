package com.example.authjwt.member;

import com.example.authjwt.user.User;
import com.example.authjwt.user.UserRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/members")
@Transactional
public class MemberController {
    private final MemberRepository memberRepository;
    private final MemberDocumentRepository documentRepository;
    private final UserRepository userRepository;
    private final ObjectMapper objectMapper;
    private final MemberFileStorage fileStorage;

    public MemberController(MemberRepository memberRepository, MemberDocumentRepository documentRepository,
                             UserRepository userRepository, ObjectMapper objectMapper, MemberFileStorage fileStorage) {
        this.memberRepository = memberRepository;
        this.documentRepository = documentRepository;
        this.userRepository = userRepository;
        this.objectMapper = objectMapper;
        this.fileStorage = fileStorage;
    }

    @GetMapping
    public List<MemberSummary> findAll(Authentication authentication) {
        requireAdmin(currentUser(authentication));
        return memberRepository.findAll().stream().map(MemberSummary::from).toList();
    }

    @GetMapping("/me")
    public MemberDetail me(Authentication authentication) {
        User user = currentUser(authentication);
        Member member = memberRepository.findByUserId(user.getId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Aucune fiche adhérent"));
        return MemberDetail.from(member);
    }

    @GetMapping("/{id}")
    public MemberDetail findOne(@PathVariable Long id, Authentication authentication) {
        Member member = findOrThrow(id);
        checkAccess(member, currentUser(authentication));
        return MemberDetail.from(member);
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public MemberDetail create(@RequestPart("data") String data,
                                @RequestPart(value = "photo", required = false) MultipartFile photo,
                                @RequestPart(value = "carteSoins", required = false) MultipartFile carteSoins,
                                @RequestPart(value = "carteMilitaire", required = false) MultipartFile carteMilitaire,
                                @RequestPart(value = "documents", required = false) List<MultipartFile> documents,
                                Authentication authentication) throws IOException {
        User user = currentUser(authentication);
        Member member = new Member();
        if (isAdmin(user)) {
            // Admin-managed adherent record, not tied to any login account.
            member.setUser(null);
        } else {
            if (memberRepository.existsByUserId(user.getId())) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "Une fiche adhérent existe déjà pour cet utilisateur");
            }
            member.setUser(user);
        }
        MemberDataDto dto = objectMapper.readValue(data, MemberDataDto.class);
        requireUnique(dto, null);
        applyData(member, dto);
        applyFiles(member, photo, carteSoins, carteMilitaire, documents, dto.typeFichier());
        return MemberDetail.from(memberRepository.save(member));
    }

    @PutMapping(value = "/{id}", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public MemberDetail update(@PathVariable Long id,
                                @RequestPart("data") String data,
                                @RequestPart(value = "photo", required = false) MultipartFile photo,
                                @RequestPart(value = "carteSoins", required = false) MultipartFile carteSoins,
                                @RequestPart(value = "carteMilitaire", required = false) MultipartFile carteMilitaire,
                                @RequestPart(value = "documents", required = false) List<MultipartFile> documents,
                                Authentication authentication) throws IOException {
        Member member = findOrThrow(id);
        checkAccess(member, currentUser(authentication));
        List<String> previousFiles = storedFileKeys(member);
        MemberDataDto dto = objectMapper.readValue(data, MemberDataDto.class);
        requireUnique(dto, id);
        applyData(member, dto);
        applyFiles(member, photo, carteSoins, carteMilitaire, documents, dto.typeFichier());
        Member saved = memberRepository.save(member);
        deleteReplacedFiles(previousFiles, saved);
        return MemberDetail.from(saved);
    }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable Long id, Authentication authentication) throws IOException {
        requireAdmin(currentUser(authentication));
        Member member = findOrThrow(id);
        List<String> files = storedFileKeys(member);
        memberRepository.delete(member);
        files.forEach(this::deleteStoredFile);
    }

    @DeleteMapping("/{id}/documents/{docId}")
    public void deleteDocument(@PathVariable Long id, @PathVariable Long docId, Authentication authentication) throws IOException {
        Member member = findOrThrow(id);
        checkAccess(member, currentUser(authentication));
        MemberDocument document = documentRepository.findById(docId)
                .filter(doc -> doc.getMember().getId().equals(id))
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Document introuvable"));
        member.getDocuments().remove(document);
        documentRepository.delete(document);
        fileStorage.delete(document.getStorageKey());
    }

    @GetMapping("/{id}/photo")
    public ResponseEntity<byte[]> photo(@PathVariable Long id, Authentication authentication) throws IOException {
        Member member = findOrThrow(id);
        checkAccess(member, currentUser(authentication));
        if (!member.hasPhoto()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Aucune photo");
        }
        return binaryResponse(readMemberFile(member.getPhotoStorageKey(), member.getLegacyPhoto()), member.getPhotoContentType());
    }

    @GetMapping("/{id}/card/{type}")
    public ResponseEntity<byte[]> card(@PathVariable Long id, @PathVariable String type, Authentication authentication) throws IOException {
        Member member = findOrThrow(id);
        checkAccess(member, currentUser(authentication));
        byte[] content;
        String contentType;
        if ("soins".equals(type)) {
            content = readMemberFile(member.getCarteSoinsStorageKey(), member.getLegacyCarteSoins());
            contentType = member.getCarteSoinsContentType();
        } else if ("militaire".equals(type)) {
            content = readMemberFile(member.getCarteMilitaireStorageKey(), member.getLegacyCarteMilitaire());
            contentType = member.getCarteMilitaireContentType();
        } else {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Type de carte invalide");
        }
        if (content == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Aucune carte");
        }
        return binaryResponse(content, contentType);
    }

    @GetMapping("/{id}/documents/{docId}")
    public ResponseEntity<byte[]> document(@PathVariable Long id, @PathVariable Long docId, Authentication authentication) throws IOException {
        Member member = findOrThrow(id);
        checkAccess(member, currentUser(authentication));
        MemberDocument document = documentRepository.findById(docId)
                .filter(doc -> doc.getMember().getId().equals(id))
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Document introuvable"));
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(document.getContentType() != null
                ? MediaType.parseMediaType(document.getContentType()) : MediaType.APPLICATION_OCTET_STREAM);
        headers.setContentDisposition(ContentDisposition.attachment().filename(document.getFilename()).build());
        byte[] content = document.getStorageKey() != null
            ? fileStorage.read(document.getStorageKey()) : document.getLegacyContent();
        if (content == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Fichier introuvable");
        return new ResponseEntity<>(content, headers, HttpStatus.OK);
    }

    private void requireUnique(MemberDataDto dto, Long currentId) {
        memberRepository.findByNumeroUnifie(dto.numeroUnifie())
                .filter(existing -> currentId == null || !existing.getId().equals(currentId))
                .ifPresent(existing -> { throw new ResponseStatusException(
                        HttpStatus.CONFLICT, "Ce numéro unifié est déjà utilisé par un autre adhérent"); });
        memberRepository.findByNomPrenom(dto.nomPrenom())
                .filter(existing -> currentId == null || !existing.getId().equals(currentId))
                .ifPresent(existing -> { throw new ResponseStatusException(
                        HttpStatus.CONFLICT, "Ce nom et prénom est déjà utilisé par un autre adhérent"); });
    }

    private void applyData(Member member, MemberDataDto dto) {
        member.setNumeroUnifie(dto.numeroUnifie());
        member.setCnr(dto.cnr());
        member.setNumeroAffiliation(dto.numeroAffiliation());
        member.setTypeService(dto.typeService());
        member.setNomPrenom(dto.nomPrenom());
        member.setGrade(dto.grade());
        member.setDateNaissance(dto.dateNaissance());
        member.setLieuNaissance(dto.lieuNaissance());
        member.setDebutActivite(dto.debutActivite());
        member.setStatut(dto.statut());
        member.setEtatCivil(dto.etatCivil());
        member.setDateMariage(dto.dateMariage());

        member.getFamilyMembers().clear();
        if (dto.familyMembers() != null) {
            for (FamilyMemberInput input : dto.familyMembers()) {
                member.getFamilyMembers().add(new FamilyMember(member, input.nom(), input.prenom(),
                        input.lienParente(), input.dateNaissance()));
            }
        }
    }

    private void applyFiles(Member member, MultipartFile photo, MultipartFile carteSoins, MultipartFile carteMilitaire,
                             List<MultipartFile> documents, String typeFichier) throws IOException {
        if (photo != null && !photo.isEmpty()) {
            member.setPhotoStorageKey(fileStorage.store(member.getNumeroUnifie(), "photo", photo.getOriginalFilename(), photo.getBytes()));
            member.setLegacyPhoto(null);
            member.setPhotoContentType(photo.getContentType());
        }
        if (carteSoins != null && !carteSoins.isEmpty()) {
            member.setCarteSoinsStorageKey(fileStorage.store(member.getNumeroUnifie(), "carte-soins", carteSoins.getOriginalFilename(), carteSoins.getBytes()));
            member.setLegacyCarteSoins(null);
            member.setCarteSoinsContentType(carteSoins.getContentType());
        }
        if (carteMilitaire != null && !carteMilitaire.isEmpty()) {
            member.setCarteMilitaireStorageKey(fileStorage.store(member.getNumeroUnifie(), "carte-militaire", carteMilitaire.getOriginalFilename(), carteMilitaire.getBytes()));
            member.setLegacyCarteMilitaire(null);
            member.setCarteMilitaireContentType(carteMilitaire.getContentType());
        }
        if (documents != null) {
            for (MultipartFile file : documents) {
                if (file.isEmpty()) continue;
                String storageKey = fileStorage.store(member.getNumeroUnifie(), "document", file.getOriginalFilename(), file.getBytes());
                member.getDocuments().add(new MemberDocument(member, typeFichier, file.getOriginalFilename(),
                        file.getContentType(), file.getSize(), storageKey));
            }
        }
    }

    private byte[] readMemberFile(String storageKey, byte[] legacyContent) throws IOException {
        if (storageKey != null) return fileStorage.read(storageKey);
        return legacyContent;
    }

    private List<String> storedFileKeys(Member member) {
        List<String> keys = new ArrayList<>();
        keys.add(member.getPhotoStorageKey());
        keys.add(member.getCarteSoinsStorageKey());
        keys.add(member.getCarteMilitaireStorageKey());
        member.getDocuments().stream().map(MemberDocument::getStorageKey).forEach(keys::add);
        return keys;
    }

    private void deleteReplacedFiles(List<String> previousFiles, Member saved) throws IOException {
        List<String> currentFiles = storedFileKeys(saved);
        for (String key : previousFiles) {
            if (key != null && !currentFiles.contains(key)) fileStorage.delete(key);
        }
    }

    private void deleteStoredFile(String key) {
        try {
            fileStorage.delete(key);
        } catch (IOException exception) {
            throw new java.io.UncheckedIOException(exception);
        }
    }

    private ResponseEntity<byte[]> binaryResponse(byte[] content, String contentType) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(contentType != null ? MediaType.parseMediaType(contentType) : MediaType.APPLICATION_OCTET_STREAM);
        return new ResponseEntity<>(content, headers, HttpStatus.OK);
    }

    private Member findOrThrow(Long id) {
        return memberRepository.findById(id).orElseThrow(this::notFound);
    }

    private User currentUser(Authentication authentication) {
        return userRepository.findByEmail(authentication.getName()).orElseThrow();
    }

    private void checkAccess(Member member, User current) {
        boolean owner = member.getUser() != null && member.getUser().getId().equals(current.getId());
        if (!owner && !isAdmin(current)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Accès refusé");
        }
    }

    private void requireAdmin(User user) {
        if (!isAdmin(user)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Accès refusé");
        }
    }

    private boolean isAdmin(User user) {
        return "ADMIN".equals(user.getRole() == null ? null : user.getRole().toUpperCase(Locale.ROOT));
    }

    private ResponseStatusException notFound() {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, "Fiche adhérent introuvable");
    }
}

record MemberSummary(Long id, String nomPrenom, LocalDate dateNaissance, String numeroUnifie,
                      String numeroAffiliation, String grade, String statut) {
    static MemberSummary from(Member member) {
        return new MemberSummary(member.getId(), member.getNomPrenom(), member.getDateNaissance(),
                member.getNumeroUnifie(), member.getNumeroAffiliation(), member.getGrade(), member.getStatut());
    }
}

record MemberDetail(Long id, String numeroUnifie, String cnr, String numeroAffiliation, String typeService,
                     String nomPrenom, String grade, LocalDate dateNaissance, String lieuNaissance,
                     LocalDate debutActivite, String statut, String etatCivil, LocalDate dateMariage,
                     boolean hasPhoto, boolean hasCarteSoins, boolean hasCarteMilitaire,
                     List<FamilyMemberDto> familyMembers, List<DocumentDto> documents) {
    static MemberDetail from(Member member) {
        List<FamilyMemberDto> family = member.getFamilyMembers().stream()
                .map(fm -> new FamilyMemberDto(fm.getId(), fm.getNom(), fm.getPrenom(), fm.getLienParente(), fm.getDateNaissance()))
                .toList();
        List<DocumentDto> docs = member.getDocuments().stream()
                .map(doc -> new DocumentDto(doc.getId(), doc.getTypeFichier(), doc.getFilename(), doc.getContentType(), doc.getSize(), doc.getCreatedAt()))
                .toList();
        return new MemberDetail(member.getId(), member.getNumeroUnifie(), member.getCnr(), member.getNumeroAffiliation(),
                member.getTypeService(), member.getNomPrenom(), member.getGrade(), member.getDateNaissance(),
                member.getLieuNaissance(), member.getDebutActivite(), member.getStatut(), member.getEtatCivil(),
                member.getDateMariage(), member.hasPhoto(), member.hasCarteSoins(),
                member.hasCarteMilitaire(), new ArrayList<>(family), new ArrayList<>(docs));
    }
}

record FamilyMemberDto(Long id, String nom, String prenom, String lienParente, LocalDate dateNaissance) {
}

record DocumentDto(Long id, String typeFichier, String filename, String contentType, long size, LocalDateTime createdAt) {
}

record FamilyMemberInput(String nom, String prenom, String lienParente, LocalDate dateNaissance) {
}

record MemberDataDto(String numeroUnifie, String cnr, String numeroAffiliation, String typeService,
                      String nomPrenom, String grade, LocalDate dateNaissance, String lieuNaissance,
                      LocalDate debutActivite, String statut, String etatCivil, LocalDate dateMariage,
                      String typeFichier, List<FamilyMemberInput> familyMembers) {
}
